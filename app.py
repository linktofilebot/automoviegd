import os
import requests
import tempfile
import threading
import json
import time
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from pymongo import MongoClient
from bson.objectid import ObjectId
import cloudinary
import cloudinary.uploader
import telebot
from telebot import types

# --- ১. গুগল ড্রাইভ লাইব্রেরি ---
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

# --- ২. কনফিগারেশন ও সেটিংস ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "moviebox_ultra_master_2026_premium")

# ডাটাবেস ও ক্লাউড সেটিংস (আপনার তথ্যসমূহ)
MONGO_URI = "mongodb+srv://Demo270:Demo270@cluster0.ls1igsg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
TMDB_API_KEY = "7dc544d9253bccc3cfecc1c677f69819"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "") # রেন্ডারে এই ভেরিয়েবলটি অবশ্যই দেবেন

cloudinary.config( 
  cloud_name = "dck0nrnt2", 
  api_key = "885392694246946", 
  api_secret = "a7y3o299JJqLfxmj9rLMK3hNbcg" 
)

bot = telebot.TeleBot(BOT_TOKEN)

# MongoDB কানেকশন ও কালেকশনস
try:
    client = MongoClient(MONGO_URI)
    db = client['moviebox_v5_db']
    movies_col, episodes_col = db['movies'], db['episodes']
    categories_col, languages_col = db['categories'], db['languages']
    ott_col, settings_col = db['ott_platforms'], db['settings']
    gdrive_col = db['gdrive_accounts'] # গুগল ড্রাইভ কালেকশন
except Exception as e:
    print(f"Database Error: {e}")

ADMIN_USER = "admin"
ADMIN_PASS = "12345"

# সাইট সেটিংস লোড ফাংশন
def get_config():
    conf = settings_col.find_one({"type": "config"})
    if not conf:
        conf = {"type": "config", "site_name": "MOVIEBOX PRO", "ad_link": "https://ad-link.com", "ad_click_limit": 2, "notice_text": "Welcome to MovieBox Pro!", "notice_color": "#00ff00", "popunder": "", "native_ad": "", "banner_ad": "", "socialbar_ad": ""}
        settings_col.insert_one(conf)
    return conf

# ডাইনামিক গুগল ড্রাইভ সার্ভিস পাওয়ার ফাংশন
def get_active_drive_service():
    active_drive = gdrive_col.find_one({"status": "active"})
    if active_drive:
        try:
            info = json.loads(active_drive['json_data'])
            creds = service_account.Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/drive'])
            return build('drive', 'v3', credentials=creds), active_drive['folder_id']
        except: return None, None
    return None, None

# --- ৩. প্রিমিয়াম CSS ---
CSS = """
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    :root { --main: #e50914; --bg: #050505; --card: #121212; --text: #ffffff; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
    .nav { background: rgba(0,0,0,0.96); padding: 15px; display: flex; justify-content: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; }
    .logo { font-size: clamp(22px, 6vw, 30px); font-weight: bold; text-decoration: none; text-transform: uppercase; background: linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000); background-size: 400% auto; -webkit-background-clip: text; background-clip: text; color: transparent; animation: rainbow 5s linear infinite; letter-spacing: 2px; }
    @keyframes rainbow { to { background-position: 400% center; } }
    .container { max-width: 1400px; margin: auto; padding: 15px; }
    .search-box { display: flex; align-items: center; background: #1a1a1a; border-radius: 25px; padding: 5px 20px; border: 1px solid #333; width: 100%; max-width: 550px; margin: 0 auto 15px; }
    .search-box input { background: transparent; border: none; color: #fff; width: 100%; padding: 10px; font-size: 15px; }
    .ott-slider { display: flex; gap: 15px; overflow-x: auto; padding: 10px 0 20px; scrollbar-width: none; }
    .ott-circle { flex: 0 0 auto; text-align: center; width: 75px; text-decoration: none; }
    .ott-circle img { width: 60px; height: 60px; border-radius: 50%; object-fit: cover; border: 2px solid #333; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 15px; }
    @media (min-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 22px; } }
    .card { background: var(--card); border-radius: 10px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; display: block; position: relative; }
    .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; }
    .card-title { padding: 10px; text-align: center; font-size: 13px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; }
    .cat-title { border-left: 5px solid var(--main); padding-left: 12px; margin: 30px 0 15px; font-size: 20px; font-weight: bold; text-transform: uppercase; }
    .btn-main { background: var(--main); color: #fff; border: none; padding: 14px 25px; border-radius: 6px; cursor: pointer; font-weight: bold; width: 100%; text-align: center; display: inline-block; text-decoration: none; }
    .drw { position: fixed; top: 0; right: -100%; width: 300px; height: 100%; background: #0a0a0a; border-left: 1px solid #333; transition: 0.4s; z-index: 2000; padding-top: 50px; overflow-y: auto; }
    .drw.active { right: 0; }
    .drw span, .drw a { padding: 18px 25px; display: block; color: #fff; text-decoration: none; border-bottom: 1px solid #222; cursor: pointer; }
    .sec-box { display: none; background: #111; padding: 20px; border-radius: 12px; margin-top: 20px; border: 1px solid #222; }
    input, select, textarea { width: 100%; padding: 12px; margin: 10px 0; background: #1a1a1a; border: 1px solid #333; color: #fff; border-radius: 6px; }
    .badge-active { background: #00ff00; color: #000; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; }
</style>
"""

# --- ৪. ফ্রন্টএন্ড রাউটস ---

@app.route('/')
def index():
    query = request.args.get('q')
    s = get_config()
    otts, cats = list(ott_col.find()), list(categories_col.find())
    if query:
        movies = list(movies_col.find({"$or": [{"title": {"$regex": query, "$options": "i"}}, {"ott": {"$regex": query, "$options": "i"}}]}).sort("_id", -1))
    else:
        movies = list(movies_col.find().sort("_id", -1))
    return render_template_string(HOME_HTML, movies=movies, otts=otts, cats=cats, query=query, s=s)

HOME_HTML = CSS + """
{{ s.popunder|safe }}
<nav class="nav"><a href="/" class="logo">{{ s.site_name }}</a></nav>
<div class="container">
    <div style="color:{{s.notice_color}}; text-align:center; margin-bottom:15px; font-weight:bold;">{{s.notice_text}}</div>
    <form action="/" method="GET" class="search-box">
        <input type="text" name="q" placeholder="Search movies, web series..." value="{{ query or '' }}">
        <button type="submit" style="background:none; border:none; color:#888;"><i class="fas fa-search"></i></button>
    </form>
    <div class="ott-slider">
        {% for o in otts %}<a href="/?q={{ o.name }}" class="ott-circle"><img src="{{ o.logo }}"></a>{% endfor %}
    </div>
    <div class="cat-title">Latest Content</div>
    <div class="grid">
        {% for m in movies %}
        <a href="/content/{{ m._id }}" class="card"><img src="{{ m.poster }}"><div class="card-title">{{ m.title }}</div></a>
        {% endfor %}
    </div>
</div>
"""

@app.route('/content/<id>')
def content_detail(id):
    m = movies_col.find_one({"_id": ObjectId(id)})
    if not m: return redirect('/')
    eps = list(episodes_col.find({"series_id": id}).sort([("season", 1), ("episode", 1)]))
    
    # ড্রাইভ এমবেড প্লেয়ার লজিক
    embed_url = m['video_url']
    is_drive = "drive.google.com" in embed_url
    if is_drive:
        try:
            file_id = embed_url.split("/d/")[1].split("/")[0]
            embed_url = f"https://drive.google.com/file/d/{file_id}/preview"
        except: pass

    return render_template_string(DETAIL_HTML, m=m, eps=eps, embed_url=embed_url, is_drive=is_drive, s=get_config())

DETAIL_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">{{ s.site_name }}</a></nav>
<div class="container">
    {% if is_drive %}
        <iframe src="{{ embed_url }}" width="100%" height="450" allow="autoplay" style="border-radius:12px; background:#000; border:none;"></iframe>
    {% else %}
        <video id="vBox" controls style="width:100%; border-radius:12px;" poster="{{ m.backdrop }}"><source src="{{ m.video_url }}" type="video/mp4"></video>
    {% endif %}
    
    {% if eps %}
    <div class="cat-title">Episodes</div>
    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap:10px;">
        {% for e in eps %}<div onclick="window.location.href='/content/{{m._id}}?ep={{e._id}}'" style="background:#222; padding:10px; text-align:center; border-radius:5px; cursor:pointer; font-size:12px;">S{{e.season}} E{{e.episode}}</div>{% endfor %}
    </div>
    {% endif %}
    
    <h1 style="margin-top:20px;">{{ m.title }} ({{ m.year }})</h1>
    <a href="{{ m.video_url }}" target="_blank" class="btn-main" style="margin-top:20px;">📥 DOWNLOAD NOW</a>
</div>
"""

# --- ৫. অ্যাডমিন প্যানেল (Google Drive Manage সহ) ---

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="sec-box" style="display:block; max-width:350px; margin:100px auto;"><h2>Admin Login</h2><input type="password" name="p" required><button class="btn-main">LOGIN</button></form></div>""")
    
    movies = list(movies_col.find().sort("_id", -1))
    gdrives = list(gdrive_col.find())
    return render_template_string(ADMIN_HTML, movies=movies, gdrives=gdrives, s=get_config())

ADMIN_HTML = CSS + """
<nav class="nav"><a href="/admin" class="logo">ADMIN PANEL</a><div style="cursor:pointer; font-size:32px; position:absolute; right:20px;" onclick="document.getElementById('drw').classList.toggle('active')">☰</div></nav>
<div class="drw" id="drw">
    <a href="/">👁️ View Site</a>
    <span onclick="openSec('manageBox')">🎬 Bulk Content / Search</span>
    <span onclick="openSec('epManageBox')">📂 Manage Episodes</span>
    <span onclick="openSec('driveBox')">☁️ Google Drive Manage</span>
    <a href="/logout" style="color:red;">Logout</a>
</div>

<div class="container">
    <!-- ১. কন্টেন্ট ম্যানেজমেন্ট ও লাইভ সার্চ -->
    <div id="manageBox" class="sec-box" style="display:block;">
        <h3>🎬 Bulk Content Search</h3>
        <input type="text" id="bulkSch" placeholder="🔍 Search movie/series name..." onkeyup="filterBulk()" style="border:1px solid var(--main);">
        <div id="bulkList" style="margin-top:15px; max-height:450px; overflow-y:auto; border:1px solid #222;">
            {% for m in movies %}
            <div class="b-item" style="padding:12px; border-bottom:1px solid #222; display:flex; justify-content:space-between; align-items:center;">
                <span>{{ m.title }}</span>
                <a href="/del_movie/{{ m._id }}" style="color:red; text-decoration:none;" onclick="return confirm('Delete?')">Delete</a>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- ২. ইপিসোড ম্যানেজমেন্ট ও সার্চ -->
    <div id="epManageBox" class="sec-box">
        <h3>📂 Manage Episodes</h3>
        <input type="text" id="epSch" placeholder="🔍 Search series..." onkeyup="filterEp()" style="border:1px solid var(--main); margin-bottom:10px;">
        <select id="sSel" onchange="loadEps(this.value)">
            <option value="">-- Select Series --</option>
            {% for m in movies if m.type == 'series' %}<option value="{{ m._id }}">{{ m.title }}</option>{% endfor %}
        </select>
        <div id="epList" style="margin-top:15px;"></div>
    </div>

    <!-- ৩. গুগল ড্রাইভ ম্যানেজমেন্ট -->
    <div id="driveBox" class="sec-box">
        <h3>☁️ Google Drive Manage</h3>
        <form action="/add_gdrive" method="POST">
            <textarea name="json_data" rows="4" placeholder="Paste Service Account JSON content..." required></textarea>
            <input type="text" name="folder_id" placeholder="Google Drive Folder ID" required>
            <button class="btn-main">Add GDrive Account</button>
        </form>
        <div style="margin-top:20px;">
            {% for g in gdrives %}
            <div style="background:#1a1a1a; padding:15px; border-radius:8px; margin-bottom:10px; border:1px solid #333; display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <b>Folder ID:</b> {{ g.folder_id }}
                    {% if g.status == 'active' %}<span class="badge-active">ACTIVE</span>{% endif %}
                </div>
                <div>
                    <a href="/activate_gdrive/{{ g._id }}" style="color:cyan; margin-right:10px;">Activate</a>
                    <a href="/del_gdrive/{{ g._id }}" style="color:red;">Delete</a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</div>

<script>
    function openSec(id){ document.querySelectorAll('.sec-box').forEach(s=>s.style.display='none'); document.getElementById(id).style.display='block'; document.getElementById('drw').classList.remove('active'); }
    function filterBulk(){
        let q = document.getElementById('bulkSch').value.toLowerCase();
        document.querySelectorAll('.b-item').forEach(i => i.style.display = i.innerText.toLowerCase().includes(q) ? 'flex' : 'none');
    }
    function filterEp(){
        let q = document.getElementById('epSch').value.toLowerCase();
        let sel = document.getElementById('sSel');
        for(let i=0; i<sel.options.length; i++) sel.options[i].style.display = sel.options[i].text.toLowerCase().includes(q) ? 'block' : 'none';
    }
    async function loadEps(sid){
        if(!sid) return;
        let r = await fetch('/api/episodes/'+sid);
        let data = await r.json();
        let div = document.getElementById('epList'); div.innerHTML = '';
        data.forEach(e => { div.innerHTML += `<div style="padding:10px; border-bottom:1px solid #222;">S${e.season} E${e.episode} <a href="/del_ep/${e._id}" style="color:red; float:right;">X</a></div>`; });
    }
</script>
"""

# --- ৬. অ্যাডমিন একশনস ---

@app.route('/login', methods=['POST'])
def login():
    if request.form['p'] == ADMIN_PASS: session['auth'] = True
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear(); return redirect('/')

@app.route('/del_movie/<id>')
def del_movie(id):
    if session.get('auth'): movies_col.delete_one({"_id": ObjectId(id)}); episodes_col.delete_many({"series_id": id})
    return redirect('/admin')

@app.route('/api/episodes/<sid>')
def get_eps_api(sid):
    eps = list(episodes_col.find({"series_id": sid}).sort([("season", 1), ("episode", 1)]))
    for e in eps: e['_id'] = str(e['_id'])
    return jsonify(eps)

@app.route('/add_gdrive', methods=['POST'])
def add_gdrive():
    if session.get('auth'):
        gdrive_col.insert_one({"json_data": request.form.get('json_data'), "folder_id": request.form.get('folder_id'), "status": "inactive"})
    return redirect('/admin')

@app.route('/activate_gdrive/<id>')
def activate_gdrive(id):
    if session.get('auth'):
        gdrive_col.update_many({}, {"$set": {"status": "inactive"}})
        gdrive_col.update_one({"_id": ObjectId(id)}, {"$set": {"status": "active"}})
    return redirect('/admin')

@app.route('/del_gdrive/<id>')
def del_gdrive(id):
    if session.get('auth'): gdrive_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

# --- ৭. টেলিগ্রাম বট লজিক (৪ জিবি সাপোর্ট + ড্রাইভ আপলোড) ---

user_data = {}

@bot.message_handler(commands=['upload'])
def cmd_upload(message):
    service, _ = get_active_drive_service()
    if not service:
        bot.send_message(message.chat.id, "❌ কোনো একটিভ গুগল ড্রাইভ পাওয়া যায়নি! অ্যাডমিন প্যানেল থেকে অ্যাড করুন।")
        return
    bot.send_message(message.chat.id, "📽️ মুভির নাম (Title) পাঠান:")
    user_data[message.chat.id] = {'state': 'SEARCH'}

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get('state') == 'SEARCH')
def bot_search(message):
    res = requests.get(f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={message.text}").json()
    if not res.get('results'):
        bot.send_message(message.chat.id, "❌ মুভি পাওয়া যায়নি!")
        return
    markup = types.InlineKeyboardMarkup()
    for m in res['results'][:5]:
        markup.add(types.InlineKeyboardButton(f"{m['title']} ({m.get('release_date','0000')[:4]})", callback_data=f"sel_{m['id']}"))
    bot.send_message(message.chat.id, "✅ মুভি সিলেক্ট করুন:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sel_'))
def bot_select(call):
    movie_id = call.data.split('_')[1]
    d = requests.get(f"https://api.themoviedb.org/3/movie/{movie_id}?api_key={TMDB_API_KEY}").json()
    user_data[call.message.chat.id].update({
        'title': d['title'], 'year': d.get('release_date','0000')[:4],
        'poster': f"https://image.tmdb.org/t/p/w500{d['poster_path']}",
        'backdrop': f"https://image.tmdb.org/t/p/original{d['backdrop_path']}",
        'state': 'LANG'
    })
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Bangla", "Hindi", "English", "Dual Audio")
    bot.send_message(call.message.chat.id, "🌐 ভাষা সিলেক্ট করুন:", reply_markup=markup)

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get('state') == 'LANG')
def bot_lang(message):
    user_data[message.chat.id]['lang'] = message.text
    user_data[message.chat.id]['state'] = 'FILE'
    bot.send_message(message.chat.id, "📁 মুভির ফাইলটি (Video/File) পাঠান।")

@bot.message_handler(content_types=['video', 'document'])
def bot_file(message):
    cid = message.chat.id
    if user_data.get(cid, {}).get('state') == 'FILE':
        bot.send_message(cid, "⏳ ফাইল পাওয়া গেছে! একটিভ গুগল ড্রাইভে আপলোড শুরু হচ্ছে...")
        try:
            file_id = message.video.file_id if message.content_type == 'video' else message.document.file_id
            file_info = bot.get_file(file_id)
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
            
            service, folder_id = get_active_drive_service()
            
            # রেন্ডারের ডিস্ক স্পেস বাঁচাতে স্ট্রিম ডাউনলোড ও আপলোড
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                r = requests.get(file_url, stream=True)
                for chunk in r.iter_content(chunk_size=1024*1024): tmp.write(chunk)
                tmp_path = tmp.name

            file_metadata = {'name': user_data[cid]['title'], 'parents': [folder_id]}
            media = MediaFileUpload(tmp_path, mimetype='video/mp4', resumable=True)
            drive_file = service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
            service.permissions().create(fileId=drive_file['id'], body={'type': 'anyone', 'role': 'viewer'}).execute()
            
            movies_col.insert_one({
                "title": user_data[cid]['title'], "year": user_data[cid]['year'],
                "poster": user_data[cid]['poster'], "backdrop": user_data[cid]['backdrop'],
                "language": user_data[cid]['lang'], "video_url": drive_file['webViewLink'], "likes": 0
            })
            bot.send_message(cid, f"✅ সফলভাবে আপলোড এবং সাইটে অ্যাড হয়েছে!\nমুভি: {user_data[cid]['title']}")
            os.remove(tmp_path)
        except Exception as e:
            bot.send_message(cid, f"❌ এরর: {str(e)}")
        user_data[cid] = {}

def run_bot():
    bot.infinity_polling()

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
