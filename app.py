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
import telebot
from telebot import types

# --- ১. গুগল ড্রাইভ লাইব্রেরি ---
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account

# --- ২. অ্যাপ কনফিগারেশন ---
app = Flask(__name__)
BOT_TOKEN = "8589295170:AAEwMMNn9NqEu1KnoWxPhVBMc1ttbCpMqgI"
app.secret_key = os.environ.get("SECRET_KEY", "moviebox_ultra_master_2026_premium")

MONGO_URI = "mongodb+srv://mesohas358:mesohas358@cluster0.6kxy1vc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
TMDB_API_KEY = "7dc544d9253bccc3cfecc1c677f69819"
SITE_URL = os.environ.get("SITE_URL", "https://moviehallbd71.onrender.com")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# MongoDB কানেকশন
try:
    client = MongoClient(MONGO_URI)
    db = client['moviebox_v5_db']
    movies_col, episodes_col = db['movies'], db['episodes']
    categories_col, languages_col = db['categories'], db['languages']
    ott_col, settings_col, comments_col = db['ott_platforms'], db['settings'], db['comments']
    gdrive_col = db['gdrive_accounts']
except Exception as e:
    print(f"Database Connection Error: {e}")

# এডমিন ক্রেডেনশিয়াল লোড
def get_admin_creds():
    creds = settings_col.find_one({"type": "admin_creds"})
    if not creds:
        creds = {"type": "admin_creds", "user": "admin", "pass": "12345"}
        settings_col.insert_one(creds)
    return creds

# সাইট সেটিংস লোড
def get_config():
    conf = settings_col.find_one({"type": "config"})
    if not conf:
        conf = {"type": "config", "site_name": "MOVIEBOX PRO", "ad_link": "https://ad-link.com", "ad_click_limit": 2, "notice_text": "Welcome to MovieBox Pro!", "notice_color": "#00ff00", "popunder": "", "native_ad": "", "banner_ad": "", "socialbar_ad": ""}
        settings_col.insert_one(conf)
    return conf

# ড্রাইভ সার্ভিস পাওয়ার ফাংশন
def get_active_drive_service():
    active_drive = gdrive_col.find_one({"status": "active"})
    if active_drive:
        try:
            info = json.loads(active_drive['json_data'])
            creds = service_account.Credentials.from_service_account_info(info, scopes=['https://www.googleapis.com/auth/drive'])
            return build('drive', 'v3', credentials=creds), active_drive['folder_id']
        except: return None, None
    return None, None

# --- ৩. প্রিমিয়াম লাইটিং CSS ---
CSS = """
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    :root { --main: #e50914; --glow: rgba(229, 9, 20, 0.7); --bg: #050505; --card: #121212; --text: #ffffff; --neon: #00f2ff; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
    .nav { background: rgba(0,0,0,0.95); padding: 18px; display: flex; justify-content: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; box-shadow: 0 0 25px var(--glow); backdrop-filter: blur(10px); }
    .logo { font-size: 30px; font-weight: 900; text-decoration: none; text-transform: uppercase; background: linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000); background-size: 400% auto; -webkit-background-clip: text; background-clip: text; color: transparent; animation: rainbow 5s linear infinite; letter-spacing: 3px; }
    @keyframes rainbow { to { background-position: 400% center; } }
    .container { max-width: 1400px; margin: auto; padding: 20px; }
    .search-box { display: flex; align-items: center; background: rgba(255,255,255,0.05); border-radius: 30px; padding: 5px 25px; border: 1px solid #333; width: 100%; max-width: 600px; margin: 0 auto 30px; transition: 0.4s; }
    .search-box input { background: transparent; border: none; color: #fff; width: 100%; padding: 12px; font-size: 16px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 20px; }
    @media (min-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 30px; } }
    .card { background: var(--card); border-radius: 18px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; transition: 0.5s; display: block; position: relative; }
    .card:hover { transform: scale(1.05); border-color: var(--neon); box-shadow: 0 15px 35px rgba(0,242,255,0.2); }
    .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; }
    .card-title { padding: 15px; text-align: center; font-size: 14px; background: linear-gradient(0deg, #000, transparent); position: absolute; bottom: 0; width: 100%; }
    .stat-card { background: #0a0a0a; padding: 30px; border-radius: 20px; text-align: center; border: 1px solid #222; }
    .btn-main { background: linear-gradient(45deg, var(--main), #ff4d4d); color: #fff; border: none; padding: 15px 30px; border-radius: 10px; cursor: pointer; font-weight: bold; width: 100%; text-align: center; display: inline-block; text-decoration: none; text-transform: uppercase; }
    .drw { position: fixed; top: 0; right: -100%; width: 320px; height: 100%; background: #050505; border-left: 1px solid #333; transition: 0.5s; z-index: 2000; padding-top: 80px; }
    .drw.active { right: 0; }
    .drw span, .drw a { padding: 20px 30px; display: block; color: #eee; text-decoration: none; border-bottom: 1px solid #111; cursor: pointer; }
    .sec-box { display: none; background: #080808; padding: 25px; border-radius: 20px; margin-top: 30px; border: 1px solid #1a1a1a; }
    iframe, video { width: 100%; border-radius: 15px; background: #000; aspect-ratio: 16/9; }
    input, select, textarea { width: 100%; padding: 12px; margin: 10px 0; background: #111; border: 1px solid #333; color: #fff; border-radius: 8px; }
    .ep-item { padding: 12px; background: #151515; margin-top: 10px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; border-left: 4px solid var(--neon); }
</style>
"""

# --- ৪. ফ্রন্টএন্ড রাউটস ---

@app.route('/', methods=['GET', 'POST'])
def index():
    # এরর ফিক্স: POST রিকোয়েস্ট আসলে যেন ৪০৫ না আসে
    if request.method == 'POST':
        return "OK", 200
        
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
    <div style="color:{{s.notice_color}}; text-align:center; margin-bottom:25px; font-weight:bold;">{{s.notice_text}}</div>
    <form action="/" method="GET" class="search-box">
        <input type="text" name="q" placeholder="Search movies & series..." value="{{ query or '' }}">
        <button type="submit" style="background:none; border:none; color:var(--neon); padding-right:15px;"><i class="fas fa-search"></i></button>
    </form>
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
    
    # এপিসোড লোড করা (সিরিজের জন্য)
    eps = list(episodes_col.find({"series_id": str(id)}).sort([("season", 1), ("episode", 1)]))
    
    # বর্তমান ভিডিও ইউআরএল (যদি কেউ এপিসোড সিলেক্ট করে)
    target_url = request.args.get('vid', m['video_url'])
    
    embed_url = target_url
    if "drive.google.com" in embed_url:
        try:
            if "/file/d/" in embed_url:
                file_id = embed_url.split("/d/")[1].split("/")[0]
            elif "id=" in embed_url:
                file_id = embed_url.split("id=")[1].split("&")[0]
            embed_url = f"https://drive.google.com/file/d/{file_id}/preview"
        except: pass
        
    return render_template_string(DETAIL_HTML, m=m, eps=eps, embed_url=embed_url, is_drive=("drive.google.com" in target_url), s=get_config())

DETAIL_HTML = CSS + """
<nav class="nav"><a href="/" class="logo">{{ s.site_name }}</a></nav>
<div class="container" style="max-width:1000px;">
    {% if is_drive %}
    <iframe src="{{ embed_url }}" allow="autoplay"></iframe>
    {% else %}
    <video id="vBox" controls poster="{{ m.backdrop }}"><source src="{{ embed_url }}" type="video/mp4"></video>
    {% endif %}
    
    <h1 style="margin-top:20px;">{{ m.title }} ({{ m.year }})</h1>
    <p style="color:#aaa;">Language: {{ m.language }}</p>

    {% if eps %}
    <div style="margin-top:30px;">
        <h3 style="color:var(--neon);">Episodes</h3>
        {% for e in eps %}
        <a href="/content/{{ m._id }}?vid={{ e.video_url }}" class="ep-item" style="text-decoration:none; color:#fff;">
            <span>S{{ e.season }} E{{ e.episode }}</span>
            <i class="fas fa-play-circle"></i>
        </a>
        {% endfor %}
    </div>
    {% endif %}

    <a href="{{ s.ad_link }}" target="_blank" class="btn-main" style="margin-top:30px;">📥 DOWNLOAD NOW</a>
</div>
"""

# --- ৫. অ্যাডমিন প্যানেল ---

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="sec-box" style="display:block; max-width:400px; margin:100px auto;"><h2 style="text-align:center;">ADMIN LOGIN</h2><input type="text" name="u" placeholder="User"><input type="password" name="p" placeholder="Pass"><button class="btn-main">LOGIN</button></form></div>""")
    
    movies = list(movies_col.find().sort("_id", -1))
    gdrives = list(gdrive_col.find())
    counts = {"movies": movies_col.count_documents({"type": "movie"}), "series": movies_col.count_documents({"type": "series"})}
    return render_template_string(ADMIN_HTML, movies=movies, gdrives=gdrives, counts=counts, s=get_config(), a=get_admin_creds())

ADMIN_HTML = CSS + """
<nav class="nav"><a href="/admin" class="logo">ADMIN</a><div style="cursor:pointer; font-size:25px; position:absolute; right:20px;" onclick="document.getElementById('drw').classList.toggle('active')">☰</div></nav>
<div class="drw" id="drw">
    <a href="/">👁️ VIEW SITE</a>
    <span onclick="openSec('manageBox')">🎬 CONTENT</span>
    <span onclick="openSec('driveBox')">☁️ G-DRIVE</span>
    <span onclick="openSec('setBox')">⚙️ SETTINGS</span>
    <a href="/logout" style="color:red;">🔴 LOGOUT</a>
</div>

<div class="container">
    <div style="display:flex; gap:15px; margin-bottom:30px;">
        <div class="stat-card" style="flex:1;"><b>{{ counts.movies }}</b><br>Movies</div>
        <div class="stat-card" style="flex:1;"><b>{{ counts.series }}</b><br>Series</div>
    </div>

    <div id="manageBox" class="sec-box" style="display:block;">
        <input type="text" id="bulkSch" placeholder="Search to delete..." onkeyup="filterBulk()">
        <div id="bulkList" style="max-height:400px; overflow-y:auto;">
            {% for m in movies %}<div class="b-item" style="padding:15px; border-bottom:1px solid #111; display:flex; justify-content:space-between;"><span>{{ m.title }}</span><a href="/del_movie/{{ m._id }}" style="color:red;">DELETE</a></div>{% endfor %}
        </div>
    </div>

    <div id="driveBox" class="sec-box">
        <form action="/add_gdrive" method="POST"><textarea name="json_data" placeholder="JSON DATA"></textarea><input type="text" name="folder_id" placeholder="Folder ID"><button class="btn-main">ADD DRIVE</button></form>
        {% for g in gdrives %}<div style="padding:10px; border:1px solid #333; margin-top:10px;">{{ g.folder_id }} - <a href="/activate_gdrive/{{ g._id }}">Activate</a></div>{% endfor %}
    </div>

    <div id="setBox" class="sec-box">
        <form action="/update_settings" method="POST">
            <input type="text" name="site_name" value="{{ s.site_name }}" placeholder="Site Name">
            <input type="text" name="notice_text" value="{{ s.notice_text }}" placeholder="Notice">
            <input type="text" name="ad_link" value="{{ s.ad_link }}" placeholder="Ad Link">
            <button class="btn-main">SAVE</button>
        </form>
    </div>
</div>
<script>
    function openSec(id){ document.querySelectorAll('.sec-box').forEach(s=>s.style.display='none'); document.getElementById(id).style.display='block'; document.getElementById('drw').classList.remove('active'); }
    function filterBulk(){ let q=document.getElementById('bulkSch').value.toLowerCase(); document.querySelectorAll('.b-item').forEach(i=>i.style.display=i.innerText.toLowerCase().includes(q)?'flex':'none'); }
</script>
"""

# --- ৬. অ্যাডমিন একশনস ---

@app.route('/login', methods=['POST'])
def login():
    creds = get_admin_creds()
    if request.form['u'] == creds['user'] and request.form['p'] == creds['pass']: session['auth'] = True; return redirect('/admin')
    return "Invalid"

@app.route('/logout')
def logout():
    session.clear(); return redirect('/admin')

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if session.get('auth'): 
        settings_col.update_one({"type": "config"}, {"$set": {
            "site_name": request.form.get('site_name'), 
            "ad_link": request.form.get('ad_link'), 
            "notice_text": request.form.get('notice_text')
        }})
    return redirect('/admin')

@app.route('/del_movie/<id>')
def del_movie(id):
    if session.get('auth'): movies_col.delete_one({"_id": ObjectId(id)}); episodes_col.delete_many({"series_id": id})
    return redirect('/admin')

@app.route('/add_gdrive', methods=['POST'])
def add_gdrive():
    if session.get('auth'): gdrive_col.insert_one({"json_data": request.form.get('json_data'), "folder_id": request.form.get('folder_id'), "status": "inactive"})
    return redirect('/admin')

@app.route('/activate_gdrive/<id>')
def activate_gdrive(id):
    if session.get('auth'): 
        gdrive_col.update_many({}, {"$set": {"status": "inactive"}})
        gdrive_col.update_one({"_id": ObjectId(id)}, {"$set": {"status": "active"}})
    return redirect('/admin')

# --- ৭. টেলিগ্রাম বট ---

@app.route('/' + BOT_TOKEN, methods=['POST'])
def get_webhook_update():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Forbidden', 403

user_data = {}

@bot.message_handler(commands=['start'])
def bot_start(message):
    bot.reply_to(message, "🎬 MOVIEBOX PRO BOT চালু আছে!\nআপলোড করতে /upload দিন।")

@bot.message_handler(commands=['upload'])
def cmd_upload(message):
    service, _ = get_active_drive_service()
    if not service: bot.send_message(message.chat.id, "❌ No Active Drive!"); return
    bot.send_message(message.chat.id, "📽️ Enter Movie/Series Name:"); user_data[message.chat.id] = {'state': 'SEARCH'}

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get('state') == 'SEARCH')
def bot_search(message):
    res = requests.get(f"https://api.themoviedb.org/3/search/multi?api_key={TMDB_API_KEY}&query={message.text}").json()
    if not res.get('results'): bot.send_message(message.chat.id, "❌ Not found!"); return
    markup = types.InlineKeyboardMarkup()
    for m in res['results'][:5]: 
        title = m.get('title') or m.get('name')
        markup.add(types.InlineKeyboardButton(f"{title} ({m.get('media_type').upper()})", callback_data=f"sel_{m['id']}_{m['media_type']}"))
    bot.send_message(message.chat.id, "✅ Select Content:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sel_'))
def bot_select(call):
    _, movie_id, m_type = call.data.split('_')
    d = requests.get(f"https://api.themoviedb.org/3/{m_type}/{movie_id}?api_key={TMDB_API_KEY}").json()
    title = d.get('title') or d.get('name')
    user_data[call.message.chat.id].update({
        'title': title, 
        'year': (d.get('release_date') or d.get('first_air_date') or "0000")[:4], 
        'poster': f"https://image.tmdb.org/t/p/w500{d['poster_path']}", 
        'backdrop': f"https://image.tmdb.org/t/p/original{d['backdrop_path']}",
        'type': 'movie' if m_type == 'movie' else 'series',
        'state': 'LANG'
    })
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True); markup.add("Bangla", "Hindi", "English", "Dual Audio")
    bot.send_message(call.message.chat.id, "🌐 Select Language:", reply_markup=markup)

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get('state') == 'LANG')
def bot_lang(message):
    user_data[message.chat.id]['lang'] = message.text; user_data[message.chat.id]['state'] = 'FILE'
    bot.send_message(message.chat.id, "📁 Send the Video File:")

@bot.message_handler(content_types=['video', 'document'])
def bot_file(message):
    cid = message.chat.id
    if user_data.get(cid, {}).get('state') == 'FILE':
        bot.send_message(cid, "🚀 Uploading to Google Drive..."); service, folder_id = get_active_drive_service()
        try:
            file_id = message.video.file_id if message.content_type == 'video' else message.document.file_id
            file_info = bot.get_file(file_id)
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
            
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                r = requests.get(file_url, stream=True)
                for chunk in r.iter_content(chunk_size=1024*1024): tmp.write(chunk)
                tmp_path = tmp.name
            
            media = MediaFileUpload(tmp_path, mimetype='video/mp4', resumable=True)
            drive_file = service.files().create(body={'name': user_data[cid]['title'], 'parents': [folder_id]}, media_body=media, fields='id, webViewLink').execute()
            service.permissions().create(fileId=drive_file['id'], body={'type': 'anyone', 'role': 'viewer'}).execute()
            
            movies_col.insert_one({
                "type": user_data[cid]['type'], 
                "title": user_data[cid]['title'], 
                "year": user_data[cid]['year'], 
                "poster": user_data[cid]['poster'], 
                "backdrop": user_data[cid]['backdrop'], 
                "language": user_data[cid]['lang'], 
                "video_url": drive_file['webViewLink']
            })
            bot.send_message(cid, f"✅ SUCCESS! Added."); os.remove(tmp_path)
        except Exception as e: bot.send_message(cid, f"❌ ERROR: {e}")
        user_data[cid] = {}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
