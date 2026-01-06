import os
import asyncio
import json
import logging
from fastapi import FastAPI, Request, Form, Query, HTTPException, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import uvicorn

# --- ১. এনভায়রনমেন্ট ভেরিয়েবলস ---
API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")
MONGO_URL = os.getenv("MONGO_URL", "your_mongodb_url")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-100123456789"))
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

# --- ২. ডাটাবেস ও বট কানেকশন ---
app = FastAPI()
db_client = AsyncIOMotorClient(MONGO_URL)
db = db_client['cinema_master_v7']
content_col = db['content']
settings_col = db['settings']
category_col = db['categories']
ott_col = db['otts']

bot = Client("movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- ৩. সেটিংস হেল্পার (যাতে Internal Server Error না আসে) ---
async def get_site_conf():
    try:
        conf = await settings_col.find_one({"type": "global"})
        if not conf:
            conf = {
                "type": "global",
                "site_name": "ULTIMATE NEON CINEMA",
                "notice": "Welcome to the world of premium entertainment! 🎬",
                "popunder": "",
                "header_banner": "",
                "ad_step_urls": "",
                "total_steps": 0
            }
            await settings_col.insert_one(conf)
        return conf
    except Exception as e:
        logging.error(f"Settings Error: {e}")
        return {"site_name": "Database Error", "notice": "Check MongoDB IP Whitelist", "total_steps": 0}

# --- ৪. আল্ট্রা নিয়ন লাইটিং ও প্রফেশনাল CSS ---
CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Poppins:wght@300;400;600&display=swap');
    :root { --primary: #00f2ff; --secondary: #bc13fe; --bg: #05070a; --card: #0d1117; --text: #e0e0e0; --glow: rgba(0, 242, 255, 0.5); }
    
    body { font-family: 'Poppins', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 0; overflow-x: hidden; }
    
    /* Neon Glow Animations */
    @keyframes neonGlow { 0% { box-shadow: 0 0 5px var(--primary); } 50% { box-shadow: 0 0 20px var(--primary); } 100% { box-shadow: 0 0 5px var(--primary); } }
    
    .header { background: rgba(13, 17, 23, 0.95); backdrop-filter: blur(15px); padding: 25px; text-align: center; border-bottom: 2px solid var(--primary); position: sticky; top:0; z-index:100; box-shadow: 0 0 20px var(--glow); }
    .header h1 { font-family: 'Orbitron', sans-serif; margin: 0; font-size: 30px; color: var(--primary); text-shadow: 0 0 10px var(--primary); letter-spacing: 3px; }
    
    .notice-bar { background: linear-gradient(90deg, var(--primary), var(--secondary)); color: #000; padding: 12px; text-align: center; font-weight: bold; font-size: 14px; box-shadow: 0 5px 15px rgba(0,0,0,0.5); }
    
    .container { max-width: 1200px; margin: auto; padding: 20px; }
    
    /* Buttons */
    .btn { background: linear-gradient(45deg, var(--primary), var(--secondary)); color: white; padding: 12px 25px; border-radius: 50px; text-decoration: none; font-weight: bold; border: none; cursor: pointer; display: inline-block; transition: 0.4s; box-shadow: 0 0 15px rgba(188, 19, 254, 0.4); }
    .btn:hover { transform: translateY(-3px) scale(1.05); box-shadow: 0 0 30px var(--primary); }
    .btn-sm { padding: 6px 15px; font-size: 12px; }

    /* OTT & Filter */
    .ott-container { display: flex; gap: 20px; overflow-x: auto; padding: 20px 0; justify-content: center; }
    .ott-card { text-align: center; text-decoration: none; color: white; min-width: 80px; transition: 0.3s; }
    .ott-card img { width: 70px; height: 70px; border-radius: 50%; border: 2px solid var(--primary); padding: 3px; background: #000; transition: 0.3s; }
    .ott-card:hover img { transform: rotate(10deg) scale(1.1); box-shadow: 0 0 20px var(--primary); }
    .badge { background: rgba(0, 242, 255, 0.1); color: var(--primary); padding: 6px 14px; border-radius: 5px; border: 1px solid var(--primary); font-size: 13px; margin: 5px; cursor: pointer; text-decoration: none; display: inline-block; }

    /* Grid & Cards */
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 25px; margin-top: 20px; }
    @media (max-width: 600px) { .grid { grid-template-columns: 1fr 1fr; gap: 10px; } }
    .card { background: var(--card); border-radius: 15px; overflow: hidden; border: 1px solid #222; transition: 0.4s; position: relative; }
    .card:hover { border-color: var(--primary); transform: translateY(-8px); box-shadow: 0 10px 30px rgba(0, 242, 255, 0.2); }
    .card img { width: 100%; height: 280px; object-fit: cover; transition: 0.5s; }
    .card:hover img { transform: scale(1.05); }
    .card-info { padding: 15px; text-align: center; }
    .card-info h4 { margin: 10px 0; font-size: 15px; height: 45px; overflow: hidden; }

    /* Details Page */
    .details-wrap { display: grid; grid-template-columns: 350px 1fr; gap: 40px; background: rgba(255,255,255,0.02); padding: 40px; border-radius: 20px; border: 1px solid #333; box-shadow: 0 0 50px rgba(0,0,0,0.5); }
    @media (max-width: 900px) { .details-wrap { grid-template-columns: 1fr; } }
    .poster-img { width: 100%; border-radius: 15px; border: 2px solid var(--primary); animation: neonGlow 3s infinite; }
    .meta-tag { display: inline-block; background: rgba(188, 19, 254, 0.1); color: #bc13fe; border: 1px solid #bc13fe; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: bold; margin: 5px; }

    /* Admin UI */
    .admin-card { background: #0d1117; padding: 30px; border-radius: 15px; margin-bottom: 30px; border-left: 5px solid var(--primary); box-shadow: 0 10px 20px rgba(0,0,0,0.3); }
    input, textarea, select { width: 100%; padding: 12px; margin: 12px 0; background: #000; color: #fff; border: 1px solid #333; border-radius: 8px; font-size: 14px; }
    input:focus { border-color: var(--primary); outline: none; box-shadow: 0 0 10px var(--primary); }
    label { font-weight: bold; color: var(--primary); }
</style>
"""

# --- ৫. ইউজার প্যানেল রুটস ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, q: str = Query(None), cat: str = Query(None), ott: str = Query(None)):
    conf = await get_site_conf()
    otts = await ott_col.find().to_list(100)
    cats = await category_col.find().to_list(100)
    
    # ডাইনামিক ফিল্টার
    query = {}
    if q: query["title"] = {"$regex": q, "$options": "i"}
    if cat: query["category"] = cat
    if ott: query["ott_id"] = ott
    
    try:
        items = await content_col.find(query).sort("_id", -1).to_list(50)
    except Exception:
        return f"<html><body style='background:#000;color:red;text-align:center;'><h1>Database Error!</h1><p>Whitelist IP 0.0.0.0/0 in MongoDB.</p></body></html>"
    
    html = f"<html><head><title>{conf['site_name']}</title><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}{conf['popunder']}</head><body>"
    html += f"<div class='header'><h1>{conf['site_name']}</h1></div>"
    if conf['notice']: html += f"<div class='notice-bar'>📢 {conf['notice']}</div>"
    
    html += "<div class='container'>"
    
    # OTT Platforms
    html += "<div class='ott-container'>"
    for o in otts:
        html += f"<a href='/?ott={o['_id']}' class='ott-card'><img src='{o['logo']}'><br><small>{o['name']}</small></a>"
    html += "</div>"
    
    # Search & Categories
    html += f"<form style='display:flex; gap:10px; margin-bottom:20px;'><input name='q' placeholder='Search movies, series, cast...' value='{q or ''}'><button class='btn'>🔍</button></form>"
    html += "<div style='text-align:center;'>"
    html += f"<a href='/' class='badge' style='background:gray; border:none; color:white;'>All</a>"
    for c in cats:
        html += f"<a href='/?cat={c['name']}' class='badge'>{c['name']}</a>"
    html += "</div>"
    
    # Grid
    html += "<div class='grid'>"
    for i in items:
        poster = i.get('poster') or "https://via.placeholder.com/300x450?text=No+Poster"
        html += f"""<div class='card'>
            <img src='{poster}'>
            <div class='card-info'>
                <h4>{i['title']}</h4>
                <a href='/movie/{i['_id']}' class='btn' style='font-size:12px; width:100%; box-sizing:border-box;'>WATCH NOW</a>
            </div>
        </div>"""
    html += "</div></div></body></html>"
    return html

@app.get("/movie/{id}", response_class=HTMLResponse)
async def movie_details(id: str):
    conf = await get_site_conf()
    item = await content_col.find_one({"_id": ObjectId(id)})
    if not item: return "<h1>Content Not Found</h1>"
    
    html = f"<html><head><title>{item['title']}</title><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}</head><body>"
    html += f"<div class='header'><h1>{conf['site_name']}</h1></div>"
    html += f"<div class='container'><div class='details-wrap'><div>"
    html += f"<img src='{item.get('poster')}' class='poster-img'>"
    if item.get('trailer'):
        yt_id = item['trailer'].split('v=')[-1].split('&')[0]
        html += f"<h3 class='neon-text'>🎬 Official Trailer</h3><iframe width='100%' height='215' src='https://www.youtube.com/embed/{yt_id}' frameborder='0' allowfullscreen style='border-radius:15px; border:1px solid var(--primary); margin-top:10px;'></iframe>"
    html += f"</div><div><h1 class='neon-text' style='margin-top:0; font-size:35px;'>{item['title']}</h1>"
    html += f"<p><span class='meta-tag'>⭐ {item.get('rating', 'N/A')}</span> <span class='meta-tag'>🌐 {item.get('language', 'N/A')}</span> <span class='meta-tag'>💎 {item.get('quality', 'HD')}</span></p>"
    html += f"<p><b>🎭 Lead Cast:</b> {item.get('actors', 'N/A')}</p>"
    html += f"<p style='color:#bbb; line-height:1.8;'><b>📝 Synopsis:</b> {item.get('description', 'No description available.')}</p>"
    
    # Links
    html += "<h2 class='neon-text' style='margin-top:40px; border-bottom:1px solid #333; padding-bottom:10px;'>📥 Download & Stream Links</h2>"
    if item['type'] == 'movie':
        for idx, q in enumerate(item.get('qualities', [])):
            html += f"<div style='margin-bottom:15px;'><a href='/verify/{id}/movie/{idx}/0' class='btn' style='width:100%; text-align:center;'>{q['quality']} - HIGH SPEED SERVER</a></div>"
    else:
        for s_idx, s in enumerate(item.get('seasons', [])):
            html += f"<h3 style='color:var(--primary); margin-top:20px;'>Season {s['s_num']}</h3>"
            for e_idx, ep in enumerate(s['episodes']):
                html += f"<div style='background:#1a1f2b; padding:15px; border-radius:12px; margin-bottom:15px;'><b>Episode {ep['e_num']}</b>: "
                for q_idx, q in enumerate(ep['qualities']):
                    html += f"<a href='/verify/{id}/series/{s_idx}_{e_idx}_{q_idx}/0' class='btn btn-sm' style='margin-left:10px;'>{q['quality']}</a>"
                html += "</div>"
    
    html += "</div></div><br><a href='/' class='btn' style='background:#222; box-shadow:none;'>⬅️ BACK TO HOME</a></div></body></html>"
    return html

# --- ৬. অ্যাডভান্সড অ্যাড-স্টেপ গেটওয়ে ---
@app.get("/verify/{id}/{ctype}/{cidx}/{step}", response_class=HTMLResponse)
async def ad_gateway(id: str, ctype: str, cidx: str, step: int):
    conf = await get_site_conf()
    total = int(conf['total_steps'])
    urls = conf['ad_step_urls'].split(",") if conf['ad_step_urls'] else []
    
    if step >= total:
        item = await content_col.find_one({"_id": ObjectId(id)})
        if ctype == 'movie': final = item['qualities'][int(cidx)]['link']
        else:
            s_i, e_i, q_i = map(int, cidx.split("_"))
            final = item['seasons'][s_i]['episodes'][e_i]['qualities'][q_i]['link']
        return RedirectResponse(url=final)

    cur_url = urls[step].strip() if step < len(urls) else "#"
    return f"""<html><head><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}</head>
    <body style='display:flex; align-items:center; justify-content:center; height:100vh; text-align:center;'>
    <div class='container'><div class='admin-card' style='display:inline-block; max-width:500px;'>
        <h2 class='neon-text'>🔐 VERIFICATION STEP {step+1}/{total}</h2>
        <p>Your link is ready! Click the button below to continue.</p>
        <div style='margin:25px 0;'>{conf.get('header_banner', '')}</div>
        <a href="{cur_url}" target="_blank" onclick="window.location.href='/verify/{id}/{ctype}/{cidx}/{step+1}'" class='btn' style='font-size:22px;'>CLICK TO CONTINUE ➡️</a>
    </div></div></body></html>"""

# --- ৭. ৩-মেনু অ্যাডমিন প্যানেল উইথ লগইন ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    auth = request.cookies.get("admin_auth")
    if auth != ADMIN_PASS:
        return f"<html><head><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}</head><body>" \
               f"<div class='container' style='max-width:400px; margin-top:100px;'><div class='admin-card'><h2>🔐 Admin Login</h2>" \
               f"<form action='/admin/login' method='post'><input type='password' name='password' placeholder='Enter Password' required><button class='btn' style='width:100%'>Login</button></form></div></div></body></html>"
    
    conf = await get_site_conf()
    otts = await ott_col.find().to_list(100)
    cats = await category_col.find().to_list(100)
    contents = await content_col.find().sort("_id", -1).to_list(15)
    
    html = f"<html><head><title>Admin Panel</title>{CSS}</head><body><div class='container'><h1 class='neon-text'>🛡️ MASTER DASHBOARD</h1>"
    
    # মেনু ১: জেনারেল সেটিংস
    html += f"""<div class='admin-card'><h3>⚙️ ১. Global Configuration</h3>
    <form action='/admin/save_settings' method='post'>
        <label>Site Name:</label><input name='site_name' value='{conf['site_name']}'>
        <label>Homepage Notice Bar:</label><textarea name='notice'>{conf['notice']}</textarea>
        <label>Total Ad Steps:</label><input type='number' name='total_steps' value='{conf['total_steps']}'>
        <label>Ad URLs (Comma Separated):</label><textarea name='ad_urls' rows='3'>{conf['ad_step_urls']}</textarea>
        <label>Popunder Ads Script:</label><textarea name='popunder' rows='3'>{conf['popunder']}</textarea>
        <button class='btn'>✅ Save Site Settings</button>
    </form></div>"""

    # মেনু ২: ট্যাক্সোনোমি (OTT & Category)
    html += f"""<div class='admin-card'><h3>📺 ২. OTT & Taxonomy</h3>
    <div style='display:grid; grid-template-columns: 1fr 1fr; gap:25px;'>
        <div>
            <h4>Add OTT Provider</h4>
            <form action='/admin/add_ott' method='post'><input name='name' placeholder='Netflix'><input name='logo' placeholder='Logo URL'><button class='btn'>➕ Add OTT</button></form>
            <div style='margin-top:10px;'>""" + "".join([f"<p>🔹 {o['name']} <a href='/admin/del_ott/{o['_id']}' style='color:red;'>[Del]</a></p>" for o in otts]) + """</div>
        </div>
        <div>
            <h4>Add Category</h4>
            <form action='/admin/add_cat' method='post'><input name='name' placeholder='Action'><button class='btn'>➕ Add Category</button></form>
            <div style='margin-top:10px;'>""" + "".join([f"<p>🔸 {c['name']} <a href='/admin/del_cat/{c['_id']}' style='color:red;'>[Del]</a></p>" for c in cats]) + """</div>
        </div>
    </div></div>"""

    # মেনু ৩: কন্টেন্ট ম্যানেজার
    html += f"""<div class='admin-card'><h3>🎬 ৩. Content Management</h3>
    <form action='/admin/add_content' method='post'>
        <div style='display:grid; grid-template-columns:1fr 1fr; gap:12px;'>
            <input name='title' placeholder='Movie Title' required><input name='poster' placeholder='Poster URL'>
            <input name='rating' placeholder='Rating (8.5)'><input name='lang' placeholder='Language'>
            <input name='actors' placeholder='Lead Cast'><input name='trailer' placeholder='Trailer URL'>
            <input name='quality' placeholder='Quality (4K)'><select name='type'><option value='movie'>Movie</option><option value='series'>Web Series</option></select>
            <select name='cat'>{"".join([f"<option value='{c['name']}'>{c['name']}</option>" for c in cats])}</select>
            <select name='ott'>{"".join([f"<option value='{o['_id']}'>{o['name']}</option>" for o in otts])}</select>
        </div>
        <textarea name='desc' placeholder='Description/Storyline'></textarea>
        <textarea name='json' rows='4' placeholder='JSON Quality Links: [{"quality":"720p","link":"url"}]'></textarea>
        <button class='btn'>🚀 PUBLISH CONTENT</button>
    </form>
    <hr style='border:1px solid #333; margin:20px 0;'>
    <h4>🗑️ Recent Content Manager</h4>
    {"".join([f"<p>🎥 {c['title']} <a href='/admin/del_con/{c['_id']}' style='color:red; margin-left:10px;'>[Delete]</a></p>" for c in contents])}
    </div>"""

    # বট স্ট্যাটাস ও বাটন
    status = "✅ ONLINE" if bot.is_connected else "❌ OFFLINE"
    html += f"<div class='admin-card'><h3>🤖 Bot Status: {status}</h3><a href='/admin/restart_bot' class='btn'>RESTART BOT</a></div>"
    
    html += "</div><div style='text-align:center; padding:20px;'><a href='/' class='btn' style='background:gray;'>⬅️ BACK TO HOME</a></div></body></html>"
    return html

# --- ৮. অ্যাডমিন অ্যাকশন হ্যান্ডলারস (Post) ---

@app.post("/admin/login")
async def admin_login_process(password: str = Form(...)):
    if password == ADMIN_PASS:
        resp = RedirectResponse(url="/admin", status_code=303)
        resp.set_cookie(key="admin_auth", value=password)
        return resp
    return "<h1>Invalid Password!</h1><a href='/admin'>Go Back</a>"

@app.post("/admin/save_settings")
async def save_settings(request: Request, site_name: str=Form(...), notice: str=Form(...), total_steps: int=Form(...), ad_urls: str=Form(...), popunder: str=Form("")):
    if request.cookies.get("admin_auth") != ADMIN_PASS: return "Unauthorized"
    await settings_col.update_one({"type": "global"}, {"$set": {"site_name": site_name, "notice": notice, "total_steps": total_steps, "ad_step_urls": ad_urls, "popunder": popunder}}, upsert=True)
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/add_content")
async def admin_add_content(request: Request, title: str=Form(...), poster: str=Form(...), rating: str=Form(...), lang: str=Form(...), actors: str=Form(...), trailer: str=Form(...), quality: str=Form(...), desc: str=Form(...), type: str=Form(...), cat: str=Form(...), ott: str=Form(...), json: str=Form(...)):
    if request.cookies.get("admin_auth") != ADMIN_PASS: return "Unauthorized"
    import json as pyjson
    try: data = pyjson.loads(json)
    except: data = []
    doc = {"title": title, "poster": poster, "rating": rating, "language": lang, "actors": actors, "trailer": trailer, "quality": quality, "description": desc, "type": type, "category": cat, "ott_id": ott}
    if type == 'movie': doc['qualities'] = data
    else: doc['seasons'] = data
    await content_col.insert_one(doc)
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/add_ott")
async def add_ott(request: Request, name: str=Form(...), logo: str=Form(...)):
    if request.cookies.get("admin_auth") != ADMIN_PASS: return "Unauthorized"
    await ott_col.insert_one({"name": name, "logo": logo})
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/add_cat")
async def add_cat(request: Request, name: str=Form(...)):
    if request.cookies.get("admin_auth") != ADMIN_PASS: return "Unauthorized"
    await category_col.insert_one({"name": name})
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/del_ott/{id}")
async def del_ott(request: Request, id: str):
    if request.cookies.get("admin_auth") != ADMIN_PASS: return "Unauthorized"
    await ott_col.delete_one({"_id": ObjectId(id)})
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/del_cat/{id}")
async def del_cat(request: Request, id: str):
    if request.cookies.get("admin_auth") != ADMIN_PASS: return "Unauthorized"
    await category_col.delete_one({"_id": ObjectId(id)})
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/del_con/{id}")
async def del_con(request: Request, id: str):
    if request.cookies.get("admin_auth") != ADMIN_PASS: return "Unauthorized"
    await content_col.delete_one({"_id": ObjectId(id)})
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/restart_bot")
async def restart_bot_api(request: Request):
    if request.cookies.get("admin_auth") != ADMIN_PASS: return "Unauthorized"
    if bot.is_connected: await bot.stop()
    asyncio.create_task(bot.start())
    return RedirectResponse(url="/admin", status_code=303)

# --- ৯. টেলিগ্রাম বট ও সার্ভার রান ---

@bot.on_message(filters.chat(CHANNEL_ID) & (filters.video | filters.document))
async def auto_post_handler(client, message):
    title = message.caption or "Automatic Post"
    link = f"https://t.me/c/{str(CHANNEL_ID)[4:]}/{message.id}"
    await content_col.insert_one({
        "title": title, "poster": "", "type": "movie", "category": "General", "ott_id": "",
        "qualities": [{"quality": "Original File", "link": link}]
    })

@app.on_event("startup")
async def on_startup():
    # বটটিকে ব্যাকগ্রাউন্ডে স্টার্ট করা হচ্ছে
    asyncio.create_task(bot.start())

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
