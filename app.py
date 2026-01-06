import os
import asyncio
import json
from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import uvicorn

# --- রেন্ডার এনভায়রনমেন্ট ভেরিয়েবলস ---
API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")
MONGO_URL = os.getenv("MONGO_URL", "your_mongodb_url")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-100123456789"))
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

# --- ডাটাবেস সেটআপ ---
app = FastAPI()
db_client = AsyncIOMotorClient(MONGO_URL)
db = db_client['cinema_pro_db']
content_col = db['content']
settings_col = db['settings']
category_col = db['categories']
ott_col = db['otts']

# --- টেলিগ্রাম বট ---
bot = Client("movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- গ্লোবাল কনফিগারেশন লোড করা ---
async def get_site_config():
    conf = await settings_col.find_one({"type": "global"})
    if not conf:
        conf = {
            "type": "global",
            "site_name": "ULTIMATE CINEMA",
            "notice": "Welcome to our advanced movie portal!",
            "popunder": "",
            "header_banner": "",
            "ad_step_urls": "",
            "total_steps": 0
        }
        await settings_col.insert_one(conf)
    return conf

# --- নিয়ন লাইটিং ও আধুনিক CSS ---
CSS = """
<style>
    :root { --primary: #00f2ff; --secondary: #bc13fe; --bg: #080a0f; --card: #111621; --text: #ffffff; }
    body { font-family: 'Poppins', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 0; }
    
    /* Glowing Neon Effects */
    .neon-text { color: var(--primary); text-shadow: 0 0 10px var(--primary), 0 0 20px var(--primary); }
    .neon-border { border: 1px solid var(--primary); box-shadow: 0 0 15px rgba(0, 242, 255, 0.3); }
    
    .header { background: rgba(17, 22, 33, 0.95); backdrop-filter: blur(15px); padding: 20px; text-align: center; border-bottom: 2px solid var(--primary); position: sticky; top:0; z-index:100; }
    .notice { background: linear-gradient(90deg, var(--primary), var(--secondary)); color: #000; padding: 10px; text-align: center; font-weight: bold; font-size: 14px; }
    
    .container { max-width: 1200px; margin: auto; padding: 20px; }
    .btn { background: linear-gradient(45deg, var(--primary), var(--secondary)); color: white; padding: 10px 25px; border-radius: 50px; text-decoration: none; font-weight: bold; border: none; cursor: pointer; display: inline-block; transition: 0.3s; box-shadow: 0 0 15px rgba(0, 242, 255, 0.4); }
    .btn:hover { transform: scale(1.05); box-shadow: 0 0 25px var(--primary); }
    
    /* Home Grid */
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 20px; margin-top: 20px; }
    @media (max-width: 600px) { .grid { grid-template-columns: 1fr 1fr; gap: 10px; } }
    .card { background: var(--card); border-radius: 15px; overflow: hidden; border: 1px solid #222; transition: 0.3s; text-align: center; position: relative; }
    .card:hover { border-color: var(--primary); transform: translateY(-5px); }
    .card img { width: 100%; height: 270px; object-fit: cover; }
    .card-title { padding: 10px; font-size: 14px; height: 40px; overflow: hidden; }

    /* OTT & Filter Icons */
    .ott-circle { width: 65px; height: 65px; border-radius: 50%; border: 2px solid var(--primary); object-fit: cover; transition: 0.3s; }
    .ott-circle:hover { box-shadow: 0 0 15px var(--primary); transform: scale(1.1); }
    
    /* Details Page Lighting */
    .details-grid { display: grid; grid-template-columns: 350px 1fr; gap: 30px; background: rgba(255,255,255,0.02); padding: 30px; border-radius: 20px; border: 1px solid #333; }
    @media (max-width: 800px) { .details-grid { grid-template-columns: 1fr; } }
    .poster-img { width: 100%; border-radius: 15px; box-shadow: 0 0 25px var(--primary); }
    .badge { background: rgba(0, 242, 255, 0.15); color: var(--primary); padding: 5px 12px; border-radius: 5px; border: 1px solid var(--primary); font-size: 13px; font-weight: bold; margin-right: 8px; }

    /* Admin Panel Styling */
    .admin-card { background: #161b22; padding: 25px; border-radius: 15px; margin-bottom: 25px; border-left: 5px solid var(--primary); }
    input, textarea, select { width: 100%; padding: 12px; margin: 10px 0; background: #0d1117; color: white; border: 1px solid #30363d; border-radius: 8px; }
    .admin-label { font-weight: bold; color: var(--primary); margin-top: 10px; display: block; }
</style>
"""

# --- রুট: হোমপেজ ---
@app.get("/", response_class=HTMLResponse)
async def homepage(q: str = Query(None), cat: str = Query(None), ott: str = Query(None)):
    conf = await get_site_config()
    otts = await ott_col.find().to_list(100)
    cats = await category_col.find().to_list(100)
    
    query = {}
    if q: query["title"] = {"$regex": q, "$options": "i"}
    if cat: query["category"] = cat
    if ott: query["ott_id"] = ott
    
    items = await content_col.find(query).sort("_id", -1).to_list(40)
    
    html = f"<html><head><title>{conf['site_name']}</title><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}{conf['popunder']}</head><body>"
    html += f"<div class='header'><h1 class='neon-text'>🚀 {conf['site_name']}</h1></div>"
    if conf['notice']: html += f"<div class='notice'>📢 {conf['notice']}</div>"
    
    html += "<div class='container'>"
    
    # OTT Platforms
    html += "<div style='display:flex; gap:20px; overflow-x:auto; padding:15px; justify-content: center;'>"
    for o in otts:
        html += f"<a href='/?ott={o['_id']}' style='text-align:center; text-decoration:none; color:white;'><img src='{o['logo']}' class='ott-circle'><br><small>{o['name']}</small></a>"
    html += "</div>"
    
    # Search & Categories
    html += f"<form style='display:flex; gap:10px; margin:20px 0;'><input name='q' placeholder='Search movies, series, stars...' value='{q or ''}'><button class='btn'>🔍 SEARCH</button></form>"
    html += "<div style='text-align:center; margin-bottom:20px;'>"
    html += f"<a href='/' class='badge' style='background:gray; color:white; border:none;'>ALL</a>"
    for c in cats:
        html += f"<a href='/?cat={c['name']}' class='badge'>{c['name']}</a>"
    html += "</div>"

    # Listing
    html += "<div class='grid'>"
    for i in items:
        poster = i.get('poster') or "https://via.placeholder.com/300x450"
        html += f"""<div class='card'>
            <img src='{poster}'>
            <div class='card-title'>{i['title']}</div>
            <div style='padding: 10px;'><a href='/movie/{i['_id']}' class='btn' style='font-size:12px; width:100%; box-sizing:border-box;'>WATCH NOW</a></div>
        </div>"""
    html += "</div></div></body></html>"
    return html

# --- রুট: ডিটেইলস পেজ ---
@app.get("/movie/{id}", response_class=HTMLResponse)
async def movie_details(id: str):
    conf = await get_site_config()
    item = await content_col.find_one({"_id": ObjectId(id)})
    if not item: return "Error: Content Not Found"
    
    html = f"<html><head><title>{item['title']}</title><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}</head><body>"
    html += f"<div class='header'><h1 class='neon-text'>{conf['site_name']}</h1></div>"
    html += f"<div class='container'><div class='details-grid'>"
    
    # Left Column: Poster & Trailer
    html += "<div>"
    html += f"<img src='{item.get('poster')}' class='poster-img'>"
    if item.get('trailer'):
        yt_id = item['trailer'].split('v=')[-1].split('&')[0]
        html += f"<h3 class='neon-text' style='margin-top:25px;'>🎬 TRAILER</h3><iframe width='100%' height='200' src='https://www.youtube.com/embed/{yt_id}' frameborder='0' allowfullscreen style='border-radius:15px; border:1px solid var(--primary);'></iframe>"
    html += "</div>"
    
    # Right Column: Info & Links
    html += "<div>"
    html += f"<h1 class='neon-text' style='margin-top:0;'>{item['title']}</h1>"
    html += f"<p><span class='badge'>⭐ {item.get('rating', 'N/A')}</span> <span class='badge'>🌐 {item.get('language', 'N/A')}</span> <span class='badge'>💎 {item.get('quality', 'HD')}</span></p>"
    html += f"<p><b>🎭 CAST:</b> {item.get('actors', 'N/A')}</p>"
    html += f"<p style='color:#ccc; line-height:1.6;'><b>📝 STORY:</b> {item.get('description', 'No description available.')}</p>"
    
    # Links
    html += "<h2 class='neon-text' style='margin-top:40px;'>📥 DOWNLOAD & STREAM</h2>"
    if item['type'] == 'movie':
        for idx, q in enumerate(item.get('qualities', [])):
            html += f"<div style='margin-bottom:12px;'><a href='/verify/{id}/movie/{idx}/0' class='btn' style='width:100%; text-align:center;'>{q['quality']} - SECURE SERVER</a></div>"
    else:
        for s_idx, s in enumerate(item.get('seasons', [])):
            html += f"<h3 style='border-bottom:2px solid var(--primary); padding-bottom:5px;'>SEASON {s['s_num']}</h3>"
            for e_idx, ep in enumerate(s['episodes']):
                html += f"<div style='background:#1a1f2b; padding:12px; border-radius:10px; margin-bottom:10px;'><b>EPISODE {ep['e_num']}</b>: "
                for q_idx, q in enumerate(ep['qualities']):
                    html += f"<a href='/verify/{id}/series/{s_idx}_{e_idx}_{q_idx}/0' class='btn' style='padding:5px 12px; font-size:12px; margin-left:8px;'>{q['quality']}</a>"
                html += "</div>"
    
    html += "</div></div>"
    html += "<br><a href='/' class='btn' style='background:#222; box-shadow:none;'>⬅️ BACK TO HOME</a></div></body></html>"
    return html

# --- রুট: অ্যাড ভেরিফিকেশন গেটওয়ে ---
@app.get("/verify/{id}/{ctype}/{cidx}/{step}", response_class=HTMLResponse)
async def verify_process(id: str, ctype: str, cidx: str, step: int):
    conf = await get_site_config()
    total = int(conf['total_steps'])
    urls = conf['ad_step_urls'].split(",")
    
    if step >= total:
        item = await content_col.find_one({"_id": ObjectId(id)})
        if ctype == 'movie': final = item['qualities'][int(cidx)]['link']
        else:
            s_i, e_i, q_i = map(int, cidx.split("_"))
            final = item['seasons'][s_i]['episodes'][e_i]['qualities'][q_i]['link']
        return RedirectResponse(url=final)

    current_ad = urls[step].strip() if step < len(urls) else "#"
    return f"""<html><head><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}</head>
    <body style='display:flex; align-items:center; justify-content:center; height:100vh; text-align:center;'>
    <div class='container'><div class='admin-card' style='display:inline-block; max-width:500px;'>
        <h2 class='neon-text'>🔐 VERIFICATION: STEP {step+1}/{total}</h2>
        <p>Click the button to unlock your final link.</p>
        <div style='margin:20px 0;'>{conf['header_banner']}</div>
        <a href="{current_ad}" target="_blank" onclick="window.location.href='/verify/{id}/{ctype}/{cidx}/{step+1}'" class='btn' style='font-size:22px;'>CLICK TO CONTINUE ➡️</a>
    </div></div></body></html>"""

# --- রুট: ৩-মেনু অ্যাডমিন প্যানেল ---
@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(q: str = Query(None)):
    conf = await get_site_config()
    otts = await ott_col.find().to_list(100)
    cats = await category_col.find().to_list(100)
    contents = await content_col.find({"title": {"$regex": q, "$options": "i"}} if q else {}).sort("_id", -1).to_list(10)
    
    html = f"<html><head><title>Admin Panel</title>{CSS}</head><body><div class='container'>"
    html += "<h1 class='neon-text'>🛡️ ADMIN CONTROL CENTER</h1>"
    
    # সেকশন ১: সাইট সেটিংস
    html += f"""<div class='admin-card'><h3>⚙️ ১. Global Configuration</h3>
    <form action='/admin/save_global' method='post'>
        <label class='admin-label'>🌐 Site Name:</label><input name='site_name' value='{conf['site_name']}'>
        <label class='admin-label'>📢 Homepage Notice:</label><textarea name='notice'>{conf['notice']}</textarea>
        <label class='admin-label'>🔢 Total Ad Steps:</label><input type='number' name='total_steps' value='{conf['total_steps']}'>
        <label class='admin-label'>🔗 Ad URLs (Comma Separated):</label><textarea name='ad_urls' rows='3'>{conf['ad_step_urls']}</textarea>
        <label class='admin-label'>🖼️ Popunder/Social Bar Script:</label><textarea name='popunder' rows='3'>{conf['popunder']}</textarea>
        <button class='btn'>✅ UPDATE ALL SETTINGS</button>
    </form></div>"""

    # সেকশন ২: ক্যাটাগরি ও ওটিটি
    html += """<div class='admin-card'><h3>📺 ২. Labels & OTT Platforms</h3>
    <div style='display:grid; grid-template-columns: 1fr 1fr; gap:25px;'>
        <div>
            <h4>➕ Add OTT Provider</h4>
            <form action='/admin/add_ott' method='post'><input name='name' placeholder='Netflix'><input name='logo' placeholder='Logo URL'><button class='btn'>ADD OTT</button></form>
            <div style='margin-top:10px;'>""" + "".join([f"<p>🔹 {o['name']} <a href='/admin/del_ott/{o['_id']}' style='color:red;'>[X]</a></p>" for o in otts]) + """</div>
        </div>
        <div>
            <h4>➕ Add Category</h4>
            <form action='/admin/add_cat' method='post'><input name='name' placeholder='Action'><button class='btn'>ADD CATEGORY</button></form>
            <div style='margin-top:10px;'>""" + "".join([f"<p>🔸 {c['name']} <a href='/admin/del_cat/{c['_id']}' style='color:red;'>[X]</a></p>" for c in cats]) + """</div>
        </div>
    </div></div>"""

    # সেকশন ৩: কন্টেন্ট ম্যানেজমেন্ট
    html += f"""<div class='admin-card'><h3>🎬 ৩. Content Manager</h3>
    <form action='/admin/add_content' method='post'>
        <div style='display:grid; grid-template-columns:1fr 1fr; gap:10px;'>
            <input name='title' placeholder='Movie Title' required>
            <input name='poster' placeholder='Poster URL'>
            <input name='rating' placeholder='Rating (8.5)'>
            <input name='lang' placeholder='Language'>
            <input name='actors' placeholder='Actors Name'>
            <input name='trailer' placeholder='Trailer URL'>
            <input name='quality' placeholder='Quality (4K)'>
            <select name='type'><option value='movie'>Movie</option><option value='series'>Series</option></select>
            <select name='cat'><option value=''>Category</option>{"".join([f"<option value='{c['name']}'>{c['name']}</option>" for c in cats])}</select>
            <select name='ott'><option value=''>OTT Provider</option>{"".join([f"<option value='{o['_id']}'>{o['name']}</option>" for o in otts])}</select>
        </div>
        <label class='admin-label'>📝 Description:</label><textarea name='desc'></textarea>
        <label class='admin-label'>📜 JSON Quality Data:</label><textarea name='json' rows='4' placeholder='[{"quality":"720p","link":"url"}]'></textarea>
        <button class='btn'>🚀 PUBLISH CONTENT</button>
    </form>
    <hr style='border:1px solid #333; margin:20px 0;'>
    <h4>🗑️ Manage Uploaded Content</h4>
    <form style='display:flex; gap:5px;'><input name='q' placeholder='Search to delete...'><button class='btn'>🔍</button></form>
    """ + "".join([f"<p>🎥 {c['title']} <a href='/admin/del_con/{c['_id']}' style='color:red; margin-left:10px;'>[Delete]</a></p>" for c in contents]) + """
    </div>"""

    html += "</div><div style='text-align:center; padding:20px;'><a href='/' class='btn' style='background:gray;'>⬅️ BACK TO HOMEPAGE</a></div></body></html>"
    return html

# --- অ্যাকশন পোস্ট হ্যান্ডলারস ---
@app.post("/admin/save_global")
async def save_global(site_name: str=Form(...), notice: str=Form(...), total_steps: int=Form(...), ad_urls: str=Form(...), popunder: str=Form("")):
    await settings_col.update_one({"type": "global"}, {"$set": {"site_name": site_name, "notice": notice, "total_steps": total_steps, "ad_step_urls": ad_urls, "popunder": popunder}})
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/add_content")
async def admin_add_content(title: str=Form(...), poster: str=Form(...), rating: str=Form(...), lang: str=Form(...), actors: str=Form(...), trailer: str=Form(...), quality: str=Form(...), desc: str=Form(...), type: str=Form(...), cat: str=Form(...), ott: str=Form(...), json: str=Form(...)):
    import json as pyjson
    data = pyjson.loads(json)
    doc = {"title": title, "poster": poster, "rating": rating, "language": lang, "actors": actors, "trailer": trailer, "quality": quality, "description": desc, "type": type, "category": cat, "ott_id": ott}
    if type == 'movie': doc['qualities'] = data
    else: doc['seasons'] = data
    await content_col.insert_one(doc)
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/add_ott")
async def admin_add_ott(name: str=Form(...), logo: str=Form(...)):
    await ott_col.insert_one({"name": name, "logo": logo})
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/del_ott/{id}")
async def admin_del_ott(id: str):
    await ott_col.delete_one({"_id": ObjectId(id)})
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/add_cat")
async def admin_add_cat(name: str=Form(...)):
    await category_col.insert_one({"name": name})
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/del_cat/{id}")
async def admin_del_cat(id: str):
    await category_col.delete_one({"_id": ObjectId(id)})
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/del_con/{id}")
async def admin_del_con(id: str):
    await content_col.delete_one({"_id": ObjectId(id)})
    return RedirectResponse(url="/admin", status_code=303)

# --- অটো আপলোড টেলিগ্রাম বট ---
@bot.on_message(filters.chat(CHANNEL_ID) & (filters.video | filters.document))
async def telegram_auto_upload(client, message):
    title = message.caption or "Automatic Upload"
    link = f"https://t.me/c/{str(CHANNEL_ID)[4:]}/{message.id}"
    await content_col.insert_one({
        "title": title, "poster": "", "type": "movie", "category": "General", "ott_id": "",
        "qualities": [{"quality": "Original Quality", "link": link}]
    })

# --- অ্যাপ স্টার্টআপ ---
@app.on_event("startup")
async def on_startup():
    await bot.start()
    print("🤖 Bot is Online!")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
