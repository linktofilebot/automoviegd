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

# --- ২. কনফিগারেশন ও সেটিংস ---
app = Flask(__name__)
# আপনার বট টোকেন সরাসরি বসিয়ে দেওয়া হয়েছে
BOT_TOKEN = "8589295170:AAHSsqlS6Zp_c-xsIAqZOv6zNiU2m_U6cro"
app.secret_key = os.environ.get("SECRET_KEY", "moviebox_ultra_master_2026_premium")

# ডাটাবেস ও এপিআই সেটিংস
MONGO_URI = "mongodb+srv://Demo270:Demo270@cluster0.ls1igsg.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
TMDB_API_KEY = "7dc544d9253bccc3cfecc1c677f69819"

bot = telebot.TeleBot(BOT_TOKEN)

# MongoDB কানেকশন
try:
    client = MongoClient(MONGO_URI)
    db = client['moviebox_v5_db']
    movies_col, episodes_col = db['movies'], db['episodes']
    categories_col, languages_col = db['categories'], db['languages']
    ott_col, settings_col = db['ott_platforms'], db['settings']
    gdrive_col = db['gdrive_accounts']
except Exception as e:
    print(f"Database Error: {e}")

ADMIN_USER = "admin"
ADMIN_PASS = "12345"

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

# --- ৩. প্রিমিয়াম লাইটিং CSS (চাহিদা অনুযায়ী) ---
CSS = """
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    :root { --main: #e50914; --glow: rgba(229, 9, 20, 0.6); --bg: #050505; --card: #121212; --text: #ffffff; --neon: cyan; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
    
    /* Rainbow Logo & Premium Nav */
    .nav { background: rgba(0,0,0,0.95); padding: 15px; display: flex; justify-content: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; box-shadow: 0 0 20px var(--glow); }
    .logo { font-size: 28px; font-weight: bold; text-decoration: none; text-transform: uppercase; background: linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000); background-size: 400% auto; -webkit-background-clip: text; background-clip: text; color: transparent; animation: rainbow 5s linear infinite; letter-spacing: 2px; text-shadow: 0 0 10px rgba(255,255,255,0.2); }
    @keyframes rainbow { to { background-position: 400% center; } }
    
    .container { max-width: 1400px; margin: auto; padding: 15px; }
    
    /* Lighting Search Box */
    .search-box { display: flex; align-items: center; background: #1a1a1a; border-radius: 25px; padding: 5px 20px; border: 1px solid #333; width: 100%; max-width: 550px; margin: 0 auto 25px; transition: 0.3s; box-shadow: inset 0 0 10px #000; }
    .search-box:focus-within { border-color: var(--main); box-shadow: 0 0 15px var(--main); }
    .search-box input { background: transparent; border: none; color: #fff; width: 100%; padding: 10px; font-size: 15px; }

    /* Premium Grid & Glow Cards */
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 20px; }
    @media (min-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 30px; } }
    .card { background: var(--card); border-radius: 15px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; transition: 0.4s; display: block; position: relative; }
    .card:hover { transform: translateY(-8px); border-color: var(--main); box-shadow: 0 10px 25px var(--glow); }
    .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; border-bottom: 2px solid #222; }
    .card-title { padding: 12px; text-align: center; font-size: 14px; font-weight: bold; text-shadow: 0 2px 4px #000; }

    /* Admin Neon Stats */
    .stat-card { background: #0f0f0f; padding: 25px; border-radius: 15px; text-align: center; border: 1px solid #333; box-shadow: 0 5px 15px #000; }
    .stat-card b { font-size: 30px; color: var(--neon); text-shadow: 0 0 10px var(--neon); }
    .stat-card span { color: #888; text-transform: uppercase; font-size: 12px; letter-spacing: 1px; }

    /* Lighting Buttons */
    .btn-main { background: var(--main); color: #fff; border: none; padding: 12px 25px; border-radius: 8px; cursor: pointer; font-weight: bold; width: 100%; text-align: center; display: inline-block; text-decoration: none; transition: 0.3s; box-shadow: 0 5px 15px var(--glow); }
    .btn-main:hover { transform: scale(1.03); box-shadow: 0 0 25px var(--main); }

    .badge-active { background: #00ff00; color: #000; padding: 3px 12px; border-radius: 6px; font-size: 11px; font-weight: bold; box-shadow: 0 0 15px #00ff00; }
    
    .drw { position: fixed; top: 0; right: -100%; width: 300px; height: 100%; background: #080808; border-left: 1px solid #333; transition: 0.4s; z-index: 2000; padding-top: 60px; box-shadow: -10px 0 40px #000; }
    .drw.active { right: 0; }
    .drw span, .drw a { padding: 20px 25px; display: block; color: #fff; text-decoration: none; border-bottom: 1px solid #1a1a1a; cursor: pointer; font-weight: 500; transition: 0.2s; }
    .drw span:hover { background: #111; color: var(--neon); border-left: 4px solid var(--neon); }

    .sec-box { display: none; background: #0d0d0d; padding: 30px; border-radius: 18px; margin-top: 25px; border: 1px solid #222; box-shadow: 0 20px 40px rgba(0,0,0,0.6); }
    iframe, video { width: 100%; border-radius: 15px; background: #000; aspect-ratio: 16/9; box-shadow: 0 0 40px rgba(0,0,0,0.9); border: 2px solid #1a1a1a; }
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
    <div style="color:{{s.notice_color}}; text-align:center; margin-bottom:20px; font-weight:bold; text-shadow: 0 0 8px {{s.notice_color}};">
        <i class="fas fa-bolt"></i> {{s.notice_text}}
    </div>
    <form action="/" method="GET" class="search-box">
        <input type="text" name="q" placeholder="Search premium movies & series..." value="{{ query or '' }}">
        <button type="submit" style="background:none; border:none; color:cyan;"><i class="fas fa-search"></i></button>
    </form>
    
    <div class="ott-slider">
        {% for o in otts %}<a href="/?q={{ o.name }}" class="ott-circle"><img src="{{ o.logo }}" title="{{ o.name }}"></a>{% endfor %}
    </div>

    <div class="cat-title" style="margin-top:40px; border-color:cyan; text-shadow: 0 0 10px cyan;">🔥 Trending Now</div>
    <div class="grid">
        {% for m in movies %}
        <a href="/content/{{ m._id }}" class="card">
            <img src="{{ m.poster }}" loading="lazy">
            <div class="card-title">{{ m.title }}</div>
        </a>
        {% endfor %}
    </div>
</div>
"""

@app.route('/content/<id>')
def content_detail(id):
    m = movies_col.find_one({"_id": ObjectId(id)})
    if not m: return redirect('/')
    eps = list(episodes_col.find({"series_id": id}).sort([("season", 1), ("episode", 1)]))
    
    embed_url = m['video_url']
    is_drive = "drive.google.com" in embed_url
    if is_drive:
        try:
            file_id = embed_url.split("/d/")[1].split("/")[0]
            embed_url = f"https://drive.google.com/file/d/{file_id}/preview"
        except: pass

    return render_template_string(DETAIL_HTML, m=m, eps=eps, embed_url=embed_url, is_drive=is_drive, s=get_config())

DETAIL_HTML = CSS + """
<nav class="nav"><a href="javascript:history.back()" style="position:absolute; left:20px; color:#fff; font-size:24px;"><i class="fas fa-chevron-left"></i></a><a href="/" class="logo">{{ s.site_name }}</a></nav>
<div class="container" style="max-width:1100px;">
    {% if is_drive %}
        <iframe src="{{ embed_url }}" allow="autoplay" scrolling="no"></iframe>
    {% else %}
        <video id="vBox" controls poster="{{ m.backdrop }}"><source src="{{ m.video_url }}" type="video/mp4"></video>
    {% endif %}
    
    <div style="margin-top:30px; border-left: 5px solid cyan; padding-left: 15px;">
        <h1 style="font-size:32px; letter-spacing:1px;">{{ m.title }} ({{ m.year }})</h1>
        <p style="color:#888; margin-top:8px;">LANGUAGE: <span style="color:cyan; font-weight:bold;">{{ m.language }}</span></p>
    </div>

    {% if eps %}
    <div class="cat-title" style="border-color:cyan;">Episodes</div>
    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap:15px;">
        {% for e in eps %}<div onclick="window.location.href='/content/{{m._id}}?ep={{e._id}}'" style="background:#1a1a1a; padding:15px; text-align:center; border-radius:10px; cursor:pointer; font-size:14px; border:1px solid #333; transition:0.3s; color:cyan;" onmouseover="this.style.background='var(--glow)'" onmouseout="this.style.background='#1a1a1a'">S{{e.season}} E{{e.episode}}</div>{% endfor %}
    </div>
    {% endif %}
    
    <button onclick="window.open('{{ s.ad_link }}'); window.location.href='{{ m.video_url }}'" class="btn-main" style="margin-top:40px; height:65px; font-size:22px; letter-spacing:2px; background:linear-gradient(45deg, #e50914, #ff4d4d);">📥 DOWNLOAD HIGH QUALITY</button>
</div>
"""

# --- ৫. অ্যাডমিন প্যানেল ---

@app.route('/admin')
def admin():
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="sec-box" style="display:block; max-width:400px; margin:100px auto; border-color:cyan; box-shadow:0 0 30px rgba(0,255,255,0.2);"><h2 style="text-align:center; margin-bottom:25px; color:cyan; letter-spacing:2px;">SECURE LOGIN</h2><input type="password" name="p" placeholder="Enter Admin Password" style="text-align:center;" required><button class="btn-main" style="background:cyan; color:#000;">ACCESS PANEL</button></form></div>""")
    
    movies = list(movies_col.find().sort("_id", -1))
    gdrives = list(gdrive_col.find())
    counts = {"movies": movies_col.count_documents({"type": "movie"}), "series": movies_col.count_documents({"type": "series"})}
    return render_template_string(ADMIN_HTML, movies=movies, gdrives=gdrives, counts=counts, s=get_config())

ADMIN_HTML = CSS + """
<nav class="nav"><a href="/admin" class="logo">ADMIN CONTROL</a><div style="cursor:pointer; font-size:32px; position:absolute; right:20px; color:cyan;" onclick="document.getElementById('drw').classList.toggle('active')">☰</div></nav>
<div class="drw" id="drw">
    <a href="/" style="background:var(--main);"><i class="fas fa-external-link-alt"></i> OPEN WEBSITE</a>
    <span onclick="openSec('manageBox')"><i class="fas fa-film"></i> MOVIE MANAGER</span>
    <span onclick="openSec('epManageBox')"><i class="fas fa-tv"></i> EPISODE MANAGER</span>
    <span onclick="openSec('driveBox')"><i class="fab fa-google-drive"></i> G-DRIVE CLOUD</span>
    <span onclick="openSec('setBox')"><i class="fas fa-tools"></i> SYSTEM SETTINGS</span>
    <a href="/logout" style="color:#ff4d4d; border-top:1px solid #333;">🔴 LOGOUT SESSION</a>
</div>

<div class="container">
    <div style="display:flex; gap:20px; margin-bottom:40px;">
        <div class="stat-card" style="flex:1;"><b>{{ counts.movies }}</b><br><span>Total Movies</span></div>
        <div class="stat-card" style="flex:1;"><b>{{ counts.series }}</b><br><span>Web Series</span></div>
    </div>

    <!-- ড্রাইভ ম্যানেজমেন্ট -->
    <div id="driveBox" class="sec-box">
        <h3 style="color:cyan; margin-bottom:20px; display:flex; align-items:center; gap:10px;"><i class="fab fa-google-drive"></i> G-DRIVE ACCOUNTS</h3>
        <form action="/add_gdrive" method="POST">
            <textarea name="json_data" rows="5" placeholder="Paste G-Drive Service Account JSON here..." style="border-color:#444;" required></textarea>
            <input type="text" name="folder_id" placeholder="Target Folder ID" required>
            <button class="btn-main" style="background:cyan; color:black;">CONNECT NEW DRIVE</button>
        </form>
        <div style="margin-top:30px;">
            {% for g in gdrives %}
            <div style="background:#161616; padding:20px; border-radius:15px; margin-bottom:15px; border:1px solid #333; display:flex; justify-content:space-between; align-items:center; box-shadow: 0 5px 15px rgba(0,0,0,0.3);">
                <div>
                    <span style="color:#555;">FOLDER ID:</span> <code style="color:cyan;">{{ g.folder_id }}</code>
                    {% if g.status == 'active' %} <span class="badge-active" style="margin-left:10px;">ACTIVE</span> {% endif %}
                </div>
                <div style="display:flex; gap:15px;">
                    <a href="/activate_gdrive/{{ g._id }}" style="color:cyan; text-decoration:none; font-weight:bold; font-size:13px;">ACTIVATE</a>
                    <a href="/del_gdrive/{{ g._id }}" style="color:#ff4d4d;" onclick="return confirm('Delete Drive?')"><i class="fas fa-trash"></i></a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- বাল্ক ম্যানেজার -->
    <div id="manageBox" class="sec-box" style="display:block;">
        <h3 style="margin-bottom:20px;">🎬 SEARCH & MANAGE CONTENT</h3>
        <input type="text" id="bulkSch" placeholder="🔍 Type movie or series name..." onkeyup="filterBulk()" style="border:1px solid #444; background:#000; height:55px; border-radius:12px;">
        <div id="bulkList" style="max-height:550px; overflow-y:auto; margin-top:20px; border:1px solid #222; border-radius:15px;">
            {% for m in movies %}
            <div class="b-item" style="padding:18px; border-bottom:1px solid #1a1a1a; display:flex; justify-content:space-between; align-items:center; transition:0.2s;" onmouseover="this.style.background='#111'" onmouseout="this.style.background='transparent'">
                <span>{{ m.title }} <small style="color:#555; margin-left:10px;">{{ m.year }}</small></span>
                <a href="/del_movie/{{ m._id }}" style="color:#ff4d4d; text-decoration:none; font-weight:bold; font-size:12px; border:1px solid #ff4d4d; padding:5px 12px; border-radius:5px;" onclick="return confirm('Delete?')">DELETE</a>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- ইপিসোড ম্যানেজার -->
    <div id="epManageBox" class="sec-box">
        <h3>📂 EPISODE MANAGER</h3>
        <select id="sSel" onchange="loadEps(this.value)" style="border-color:cyan; height:55px; background:#000;">
            <option value="">-- SELECT SERIES TO MANAGE --</option>
            {% for m in movies if m.type == 'series' %}<option value="{{ m._id }}">{{ m.title }}</option>{% endfor %}
        </select>
        <div id="epList" style="margin-top:25px;"></div>
    </div>

    <!-- সেটিংস -->
    <div id="setBox" class="sec-box">
        <h3>⚙️ GENERAL SYSTEM SETTINGS</h3>
        <form action="/update_settings" method="POST">
            <label style="color:#666;">SITE NAME</label><input type="text" name="site_name" value="{{ s.site_name }}">
            <label style="color:#666;">DOWNLOAD / AD LINK</label><input type="text" name="ad_link" value="{{ s.ad_link }}">
            <label style="color:#666;">NOTICE TEXT</label><input type="text" name="notice_text" value="{{ s.notice_text }}">
            <button class="btn-main" style="margin-top:20px;">SAVE ALL CHANGES</button>
        </form>
    </div>
</div>

<script>
    function openSec(id){ document.querySelectorAll('.sec-box').forEach(s=>s.style.display='none'); document.getElementById(id).style.display='block'; document.getElementById('drw').classList.remove('active'); }
    function filterBulk(){
        let q = document.getElementById('bulkSch').value.toLowerCase();
        document.querySelectorAll('.b-item').forEach(i => i.style.display = i.innerText.toLowerCase().includes(q) ? 'flex' : 'none');
    }
    async function loadEps(sid){
        if(!sid) return;
        let r = await fetch('/api/episodes/'+sid);
        let data = await r.json();
        let div = document.getElementById('epList'); div.innerHTML = '';
        if(data.length == 0) div.innerHTML = '<p style="color:#555;">No episodes found for this series.</p>';
        data.forEach(e => {
            div.innerHTML += `<div style="padding:18px; border-bottom:1px solid #222; display:flex; justify-content:space-between; background:#111; margin-bottom:8px; border-radius:12px; border:1px solid #333;">
                <span>SEASON ${e.season} - EPISODE ${e.episode}</span>
                <a href="/del_ep/${e._id}" style="color:#ff4d4d; text-decoration:none; font-weight:bold;">REMOVE</a>
            </div>`;
        });
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

@app.route('/update_settings', methods=['POST'])
def update_settings():
    if session.get('auth'):
        settings_col.update_one({"type": "config"}, {"$set": {"site_name": request.form.get('site_name'), "ad_link": request.form.get('ad_link'), "notice_text": request.form.get('notice_text')}})
    return redirect('/admin')

@app.route('/del_ep/<id>')
def del_ep(id):
    if session.get('auth'): episodes_col.delete_one({"_id": ObjectId(id)})
    return redirect('/admin')

# --- ৭. টেলিগ্রাম বট লজিক (৪ জিবি সাপোর্ট + ড্রাইভ আপলোড) ---

user_data = {}

@bot.message_handler(commands=['upload'])
def cmd_upload(message):
    service, _ = get_active_drive_service()
    if not service:
        bot.send_message(message.chat.id, "❌ No Active Google Drive found! Add one from Admin Panel.")
        return
    bot.send_message(message.chat.id, "📽️ Enter Movie Name (Title):")
    user_data[message.chat.id] = {'state': 'SEARCH'}

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get('state') == 'SEARCH')
def bot_search(message):
    res = requests.get(f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={message.text}").json()
    if not res.get('results'):
        bot.send_message(message.chat.id, "❌ Movie not found! Try again.")
        return
    markup = types.InlineKeyboardMarkup()
    for m in res['results'][:5]:
        markup.add(types.InlineKeyboardButton(f"{m['title']} ({m.get('release_date','0000')[:4]})", callback_data=f"sel_{m['id']}"))
    bot.send_message(message.chat.id, "✅ Select the correct movie:", reply_markup=markup)

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
    bot.send_message(call.message.chat.id, "🌐 Select Language:", reply_markup=markup)

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get('state') == 'LANG')
def bot_lang(message):
    user_data[message.chat.id]['lang'] = message.text
    user_data[message.chat.id]['state'] = 'FILE'
    bot.send_message(message.chat.id, "📁 Send the Video File (Max 4GB):")

@bot.message_handler(content_types=['video', 'document'])
def bot_file(message):
    cid = message.chat.id
    if user_data.get(cid, {}).get('state') == 'FILE':
        bot.send_message(cid, "⏳ File received! Uploading to Google Drive... Please wait.")
        try:
            file_id = message.video.file_id if message.content_type == 'video' else message.document.file_id
            file_info = bot.get_file(file_id)
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
            
            service, folder_id = get_active_drive_service()
            
            # Use temp file for streaming transfer to save server RAM
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
            bot.send_message(cid, f"✅ SUCCESS! '{user_data[cid]['title']}' added to site.")
            os.remove(tmp_path)
        except Exception as e:
            bot.send_message(cid, f"❌ ERROR: {str(e)}")
        user_data[cid] = {}

def run_bot():
    bot.infinity_polling()

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
