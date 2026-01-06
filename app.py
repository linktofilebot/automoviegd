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
MONGO_URI = "mongodb+srv://mesohas358:mesohas358@cluster0.6kxy1vc.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
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

# এডমিন ক্রেডেনশিয়াল লোড ফাংশন (DB + Env)
def get_admin_creds():
    creds = settings_col.find_one({"type": "admin_creds"})
    if not creds:
        creds = {
            "type": "admin_creds",
            "user": os.environ.get("ADMIN_USER", "admin"),
            "pass": os.environ.get("ADMIN_PASS", "12345")
        }
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

# --- ৩. প্রিমিয়াম লাইটিং CSS (Extreme Premium) ---
CSS = """
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
<style>
    :root { --main: #e50914; --glow: rgba(229, 9, 20, 0.7); --bg: #050505; --card: #121212; --text: #ffffff; --neon: #00f2ff; }
    * { box-sizing: border-box; margin: 0; padding: 0; outline: none; }
    body { font-family: 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); overflow-x: hidden; }
    
    /* Rainbow Glow Nav */
    .nav { background: rgba(0,0,0,0.95); padding: 18px; display: flex; justify-content: center; border-bottom: 2px solid var(--main); position: sticky; top: 0; z-index: 1000; box-shadow: 0 0 25px var(--glow); backdrop-filter: blur(10px); }
    .logo { font-size: 30px; font-weight: 900; text-decoration: none; text-transform: uppercase; background: linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000); background-size: 400% auto; -webkit-background-clip: text; background-clip: text; color: transparent; animation: rainbow 5s linear infinite; letter-spacing: 3px; filter: drop-shadow(0 0 5px rgba(255,255,255,0.3)); }
    @keyframes rainbow { to { background-position: 400% center; } }
    
    .container { max-width: 1400px; margin: auto; padding: 20px; }
    
    /* Neon Search Box */
    .search-box { display: flex; align-items: center; background: rgba(255,255,255,0.05); border-radius: 30px; padding: 5px 25px; border: 1px solid #333; width: 100%; max-width: 600px; margin: 0 auto 30px; transition: 0.4s; box-shadow: 0 5px 15px rgba(0,0,0,0.5); }
    .search-box:focus-within { border-color: var(--neon); box-shadow: 0 0 20px rgba(0,242,255,0.4); }
    .search-box input { background: transparent; border: none; color: #fff; width: 100%; padding: 12px; font-size: 16px; }

    /* Premium Glow Cards */
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 20px; }
    @media (min-width: 600px) { .grid { grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 30px; } }
    .card { background: var(--card); border-radius: 18px; overflow: hidden; border: 1px solid #222; text-decoration: none; color: #fff; transition: 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275); display: block; position: relative; }
    .card:hover { transform: scale(1.05); border-color: var(--neon); box-shadow: 0 15px 35px rgba(0,242,255,0.2); }
    .card img { width: 100%; aspect-ratio: 2/3; object-fit: cover; }
    .card-title { padding: 15px; text-align: center; font-size: 15px; font-weight: 600; background: linear-gradient(0deg, #000, transparent); position: absolute; bottom: 0; width: 100%; }

    /* Admin Cyperpunk Stats */
    .stat-card { background: #0a0a0a; padding: 30px; border-radius: 20px; text-align: center; border: 1px solid #222; box-shadow: 0 10px 20px #000; position: relative; overflow: hidden; }
    .stat-card::after { content: ''; position: absolute; top:0; left:0; width:100%; height:3px; background: var(--neon); box-shadow: 0 0 15px var(--neon); }
    .stat-card b { font-size: 35px; color: var(--neon); text-shadow: 0 0 10px var(--neon); }
    .stat-card span { color: #aaa; text-transform: uppercase; font-size: 13px; letter-spacing: 2px; display: block; margin-top: 5px; }

    /* Buttons & Badges */
    .btn-main { background: linear-gradient(45deg, var(--main), #ff4d4d); color: #fff; border: none; padding: 15px 30px; border-radius: 10px; cursor: pointer; font-weight: bold; width: 100%; text-align: center; display: inline-block; text-decoration: none; transition: 0.3s; text-transform: uppercase; box-shadow: 0 5px 20px var(--glow); border: 1px solid rgba(255,255,255,0.1); }
    .btn-main:hover { transform: translateY(-3px); box-shadow: 0 8px 25px var(--main); filter: brightness(1.2); }
    .badge-active { background: #00ff00; color: #000; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 800; box-shadow: 0 0 15px #00ff00; text-transform: uppercase; }
    
    .drw { position: fixed; top: 0; right: -100%; width: 320px; height: 100%; background: #050505; border-left: 1px solid #333; transition: 0.5s cubic-bezier(0.4, 0, 0.2, 1); z-index: 2000; padding-top: 80px; box-shadow: -20px 0 60px #000; }
    .drw.active { right: 0; }
    .drw span, .drw a { padding: 22px 30px; display: block; color: #eee; text-decoration: none; border-bottom: 1px solid #111; cursor: pointer; font-size: 16px; transition: 0.3s; }
    .drw span:hover { background: #111; color: var(--neon); padding-left: 40px; }

    .sec-box { display: none; background: #080808; padding: 35px; border-radius: 25px; margin-top: 30px; border: 1px solid #1a1a1a; box-shadow: 0 30px 60px rgba(0,0,0,0.8); }
    iframe, video { width: 100%; border-radius: 20px; background: #000; aspect-ratio: 16/9; box-shadow: 0 0 50px rgba(0,0,0,1); border: 2px solid #111; }
    
    input, select, textarea { width: 100%; padding: 15px; margin: 12px 0; background: #111; border: 1px solid #333; color: #fff; border-radius: 10px; font-size: 15px; transition: 0.3s; }
    input:focus { border-color: var(--neon); background: #151515; }
    label { color: #666; font-size: 12px; text-transform: uppercase; font-weight: bold; margin-left: 5px; }
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
    <div style="color:{{s.notice_color}}; text-align:center; margin-bottom:25px; font-weight:bold; text-shadow: 0 0 10px {{s.notice_color}};">
        <i class="fas fa-fire"></i> {{s.notice_text}}
    </div>
    <form action="/" method="GET" class="search-box">
        <input type="text" name="q" placeholder="Search by name, platform, genre..." value="{{ query or '' }}">
        <button type="submit" style="background:none; border:none; color:var(--neon); font-size:18px;"><i class="fas fa-search"></i></button>
    </form>
    
    <div class="ott-slider">
        {% for o in otts %}<a href="/?q={{ o.name }}" class="ott-circle"><img src="{{ o.logo }}" title="{{ o.name }}"></a>{% endfor %}
    </div>

    <div class="cat-title" style="margin-top:40px; border-color:var(--neon); text-shadow: 0 0 10px var(--neon);">💎 Recommended For You</div>
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
<nav class="nav"><a href="javascript:history.back()" style="position:absolute; left:20px; color:#fff; font-size:24px;"><i class="fas fa-arrow-left"></i></a><a href="/" class="logo">{{ s.site_name }}</a></nav>
<div class="container" style="max-width:1100px;">
    {% if is_drive %}
        <iframe src="{{ embed_url }}" allow="autoplay" scrolling="no"></iframe>
    {% else %}
        <video id="vBox" controls poster="{{ m.backdrop }}"><source src="{{ m.video_url }}" type="video/mp4"></video>
    {% endif %}
    
    <div style="margin-top:35px; background: rgba(255,255,255,0.03); padding: 20px; border-radius: 15px; border-left: 5px solid var(--neon);">
        <h1 style="font-size:32px; letter-spacing:1px; text-shadow: 0 0 15px rgba(255,255,255,0.2);">{{ m.title }} ({{ m.year }})</h1>
        <p style="color:#888; margin-top:10px; font-size:16px;">QUALITY: <span style="color:var(--neon); font-weight:bold;">PREMIUM ULTRA HD</span> | LANG: <span style="color:var(--neon); font-weight:bold;">{{ m.language }}</span></p>
    </div>

    {% if eps %}
    <div class="cat-title" style="border-color:var(--neon);">Episodes Collection</div>
    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap:15px;">
        {% for e in eps %}<div onclick="window.location.href='/content/{{m._id}}?ep={{e._id}}'" style="background:#111; padding:18px; text-align:center; border-radius:12px; cursor:pointer; font-size:14px; border:1px solid #222; transition:0.3s; color:var(--neon); font-weight:bold;" onmouseover="this.style.background='var(--neon)'; this.style.color='#000'; this.style.boxShadow='0 0 15px var(--neon)'" onmouseout="this.style.background='#111'; this.style.color='var(--neon)'; this.style.boxShadow='none'">S{{e.season}} E{{e.episode}}</div>{% endfor %}
    </div>
    {% endif %}
    
    <button onclick="window.open('{{ s.ad_link }}'); window.location.href='{{ m.video_url }}'" class="btn-main" style="margin-top:40px; height:70px; font-size:22px; letter-spacing:2px;">📥 DOWNLOAD HIGH SPEED</button>
</div>
"""

# --- ৫. অ্যাডমিন প্যানেল ---

@app.route('/admin')
def admin():
    creds = get_admin_creds()
    if not session.get('auth'):
        return render_template_string(CSS + """<div class="container"><form action="/login" method="POST" class="sec-box" style="display:block; max-width:450px; margin:100px auto; border-color:var(--neon); box-shadow:0 0 40px rgba(0,242,255,0.2);"><h2 style="text-align:center; margin-bottom:30px; color:var(--neon); letter-spacing:3px; font-weight:900;">MASTER ACCESS</h2><input type="text" name="u" placeholder="Username" required><input type="password" name="p" placeholder="Password" required><button class="btn-main" style="background:var(--neon); color:#000;">UNLOCK PANEL</button></form></div>""")
    
    movies = list(movies_col.find().sort("_id", -1))
    gdrives = list(gdrive_col.find())
    counts = {"movies": movies_col.count_documents({"type": "movie"}), "series": movies_col.count_documents({"type": "series"})}
    return render_template_string(ADMIN_HTML, movies=movies, gdrives=gdrives, counts=counts, s=get_config(), a=creds)

ADMIN_HTML = CSS + """
<nav class="nav"><a href="/admin" class="logo">CONTROL CENTER</a><div style="cursor:pointer; font-size:32px; position:absolute; right:20px; color:var(--neon);" onclick="document.getElementById('drw').classList.toggle('active')">☰</div></nav>
<div class="drw" id="drw">
    <a href="/" style="background:var(--main); font-weight:bold;"><i class="fas fa-eye"></i> VISIT SITE</a>
    <span onclick="openSec('manageBox')"><i class="fas fa-film"></i> CONTENT DATABASE</span>
    <span onclick="openSec('epManageBox')"><i class="fas fa-play-circle"></i> EPISODE MANAGER</span>
    <span onclick="openSec('driveBox')"><i class="fab fa-google-drive"></i> CLOUD STORAGE</span>
    <span onclick="openSec('setBox')"><i class="fas fa-user-shield"></i> SECURITY & SETTINGS</span>
    <a href="/logout" style="color:#ff4d4d; border-top:1px solid #222;">🔴 TERMINATE SESSION</a>
</div>

<div class="container">
    <div style="display:flex; gap:20px; margin-bottom:40px;">
        <div class="stat-card" style="flex:1;"><b>{{ counts.movies }}</b><br><span>MOVIES</span></div>
        <div class="stat-card" style="flex:1;"><b>{{ counts.series }}</b><br><span>SERIES</span></div>
    </div>

    <!-- সিকিউরিটি ও জেনারেল সেটিংস -->
    <div id="setBox" class="sec-box">
        <h3 style="color:var(--neon); margin-bottom:20px;"><i class="fas fa-shield-alt"></i> SECURITY & AUTH</h3>
        <form action="/update_admin" method="POST" style="background:#111; padding:20px; border-radius:15px; border:1px solid #222; margin-bottom:30px;">
            <label>ADMIN USERNAME</label><input type="text" name="new_user" value="{{ a.user }}">
            <label>ADMIN PASSWORD</label><input type="text" name="new_pass" value="{{ a.pass }}">
            <button class="btn-main" style="background:var(--neon); color:#000;">UPDATE LOGIN CREDS</button>
        </form>

        <h3 style="color:var(--neon); margin-bottom:20px;"><i class="fas fa-cog"></i> SITE CONFIG</h3>
        <form action="/update_settings" method="POST">
            <label>SITE NAME</label><input type="text" name="site_name" value="{{ s.site_name }}">
            <label>GLOBAL AD LINK</label><input type="text" name="ad_link" value="{{ s.ad_link }}">
            <label>NOTIFICATION BAR</label><input type="text" name="notice_text" value="{{ s.notice_text }}">
            <button class="btn-main">SAVE SYSTEM SETTINGS</button>
        </form>
    </div>

    <!-- ড্রাইভ ম্যানেজার -->
    <div id="driveBox" class="sec-box">
        <h3 style="color:var(--neon); margin-bottom:20px;"><i class="fab fa-google-drive"></i> CLOUD DRIVE MANAGEMENT</h3>
        <form action="/add_gdrive" method="POST">
            <textarea name="json_data" rows="5" placeholder="Paste Service Account JSON content here..." required></textarea>
            <input type="text" name="folder_id" placeholder="Google Drive Folder ID" required>
            <button class="btn-main" style="background:cyan; color:black;">CONNECT CLOUD DRIVE</button>
        </form>
        <div style="margin-top:30px;">
            {% for g in gdrives %}
            <div style="background:#111; padding:20px; border-radius:15px; margin-bottom:15px; border:1px solid #333; display:flex; justify-content:space-between; align-items:center;">
                <div style="font-family:monospace;">
                    <span style="color:#555;">FOLDER_ID:</span> {{ g.folder_id }}
                    {% if g.status == 'active' %} <span class="badge-active" style="margin-left:15px;">ACTIVE</span> {% endif %}
                </div>
                <div>
                    <a href="/activate_gdrive/{{ g._id }}" style="color:var(--neon); text-decoration:none; font-weight:bold; margin-right:20px;">ACTIVATE</a>
                    <a href="/del_gdrive/{{ g._id }}" style="color:#ff4d4d;" onclick="return confirm('Erase drive data?')"><i class="fas fa-trash"></i></a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- কন্টেন্ট ম্যানেজার -->
    <div id="manageBox" class="sec-box" style="display:block;">
        <h3 style="margin-bottom:20px;">🎬 MOVIE & SERIES DATABASE</h3>
        <input type="text" id="bulkSch" placeholder="🔍 Instant search in database..." onkeyup="filterBulk()" style="background:#000; height:60px; border-radius:15px; border-color:#333;">
        <div id="bulkList" style="max-height:600px; overflow-y:auto; margin-top:20px; border:1px solid #1a1a1a; border-radius:15px;">
            {% for m in movies %}
            <div class="b-item" style="padding:20px; border-bottom:1px solid #111; display:flex; justify-content:space-between; align-items:center; transition:0.3s;" onmouseover="this.style.background='rgba(0,242,255,0.05)'" onmouseout="this.style.background='transparent'">
                <span style="font-weight:600;">{{ m.title }} <small style="color:#444; margin-left:10px;">{{ m.year }}</small></span>
                <a href="/del_movie/{{ m._id }}" style="color:#ff4d4d; text-decoration:none; font-weight:bold; border:1px solid #ff4d4d; padding:6px 15px; border-radius:8px;" onclick="return confirm('Delete forever?')">DELETE</a>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- ইপিসোড ম্যানেজার -->
    <div id="epManageBox" class="sec-box">
        <h3>📂 SERIES EPISODE CONTROL</h3>
        <select id="sSel" onchange="loadEps(this.value)" style="height:60px; background:#000; border-color:var(--neon);">
            <option value="">-- SELECT WEB SERIES --</option>
            {% for m in movies if m.type == 'series' %}<option value="{{ m._id }}">{{ m.title }}</option>{% endfor %}
        </select>
        <div id="epList" style="margin-top:25px;"></div>
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
        if(data.length == 0) div.innerHTML = '<p style="color:#444; text-align:center; padding:20px;">No episodes found for this series.</p>';
        data.forEach(e => {
            div.innerHTML += `<div style="padding:20px; border-bottom:1px solid #222; display:flex; justify-content:space-between; background:#111; margin-bottom:10px; border-radius:15px;">
                <span style="color:var(--neon);">SEASON ${e.season} - EPISODE ${e.episode}</span>
                <a href="/del_ep/${e._id}" style="color:#ff4d4d; text-decoration:none; font-weight:bold;">REMOVE</a>
            </div>`;
        });
    }
</script>
"""

# --- ৬. অ্যাডমিন একশনস (Auth Fix) ---

@app.route('/login', methods=['POST'])
def login():
    creds = get_admin_creds()
    if request.form['u'] == creds['user'] and request.form['p'] == creds['pass']:
        session['auth'] = True
        return redirect('/admin')
    return "Invalid Credentials"

@app.route('/logout')
def logout():
    session.clear(); return redirect('/')

@app.route('/update_admin', methods=['POST'])
def update_admin():
    if session.get('auth'):
        settings_col.update_one({"type": "admin_creds"}, {"$set": {
            "user": request.form.get('new_user'),
            "pass": request.form.get('new_pass')
        }})
    return redirect('/admin')

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

# --- ৭. টেলিগ্রাম বট লজিক (৪ জিবি + ড্রাইভ আপলোড) ---

user_data = {}

@bot.message_handler(commands=['upload'])
def cmd_upload(message):
    service, _ = get_active_drive_service()
    if not service:
        bot.send_message(message.chat.id, "❌ No Active Drive! Go to Admin Panel > Cloud Drive and activate one.")
        return
    bot.send_message(message.chat.id, "🎬 Movie Upload Started!\nEnter Movie Name:")
    user_data[message.chat.id] = {'state': 'SEARCH'}

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get('state') == 'SEARCH')
def bot_search(message):
    res = requests.get(f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={message.text}").json()
    if not res.get('results'):
        bot.send_message(message.chat.id, "❌ No results found on TMDB.")
        return
    markup = types.InlineKeyboardMarkup()
    for m in res['results'][:5]:
        markup.add(types.InlineKeyboardButton(f"{m['title']} ({m.get('release_date','0000')[:4]})", callback_data=f"sel_{m['id']}"))
    bot.send_message(message.chat.id, "✅ Select Movie from TMDB:", reply_markup=markup)

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
    bot.send_message(message.chat.id, "📁 Upload the Video File now (Up to 4GB):")

@bot.message_handler(content_types=['video', 'document'])
def bot_file(message):
    cid = message.chat.id
    if user_data.get(cid, {}).get('state') == 'FILE':
        bot.send_message(cid, "🚀 File received! Streaming to Google Drive... Please wait.")
        try:
            file_id = message.video.file_id if message.content_type == 'video' else message.document.file_id
            file_info = bot.get_file(file_id)
            file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
            
            service, folder_id = get_active_drive_service()
            
            # Use temp file for streaming transfer
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
            bot.send_message(cid, f"✅ SUCCESS! '{user_data[cid]['title']}' is now live on the site.")
            os.remove(tmp_path)
        except Exception as e:
            bot.send_message(cid, f"❌ ERROR: {str(e)}")
        user_data[cid] = {}

def run_bot():
    bot.infinity_polling()

if __name__ == '__main__':
    threading.Thread(target=run_bot, daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
