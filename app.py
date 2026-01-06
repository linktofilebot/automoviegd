import os
import asyncio
import json
from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import uvicorn

# --- কনফিগারেশন (Render-এর Environment Variables থেকে আসবে) ---
API_ID = int(os.getenv("API_ID", "123456"))
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")
MONGO_URL = os.getenv("MONGO_URL", "your_mongodb_url")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-100123456789"))

# --- অ্যাপ ও ডাটাবেস ইনিশিয়ালাইজ ---
app = FastAPI()
db_client = AsyncIOMotorClient(MONGO_URL)
db = db_client['ultimate_movie_db']
content_col = db['content']
settings_col = db['settings']
category_col = db['categories']
ott_col = db['otts']

bot = Client("movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- গ্লোবাল সেটিংস লোডার ---
async def get_config():
    conf = await settings_col.find_one({"type": "global"})
    if not conf:
        conf = {
            "type": "global", 
            "site_name": "NEON CINEMA", 
            "notice": "Welcome to our premium movie portal!", 
            "popunder": "", 
            "ad_step_urls": "", 
            "total_steps": 0
        }
        await settings_col.insert_one(conf)
    return conf

# --- নিয়ন লাইটিং ও প্রফেশনাল CSS ---
CSS = """
<style>
    :root { --primary: #00f2ff; --secondary: #7000ff; --bg: #05070a; --card: #10141d; --text: #ffffff; }
    body { font-family: 'Poppins', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 0; }
    
    /* Lighting UI Components */
    .neon-text { color: var(--primary); text-shadow: 0 0 10px var(--primary), 0 0 20px var(--primary); }
    .neon-border { border: 1px solid var(--primary); box-shadow: 0 0 15px rgba(0, 242, 255, 0.2); }
    .header { background: rgba(16, 20, 29, 0.9); backdrop-filter: blur(10px); padding: 15px; text-align: center; border-bottom: 2px solid var(--primary); position: sticky; top:0; z-index:100; }
    .notice { background: linear-gradient(90deg, var(--primary), var(--secondary)); color: #000; padding: 10px; text-align: center; font-weight: bold; font-size: 14px; }
    
    .container { max-width: 1200px; margin: auto; padding: 15px; }
    .btn { background: linear-gradient(45deg, var(--primary), var(--secondary)); color: white; padding: 10px 20px; border-radius: 50px; text-decoration: none; font-weight: bold; border: none; cursor: pointer; display: inline-block; transition: 0.3s; box-shadow: 0 0 10px rgba(0, 242, 255, 0.5); }
    .btn:hover { transform: scale(1.05); box-shadow: 0 0 20px var(--primary); }
    
    /* Grid & Cards */
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; margin-top: 20px; }
    @media (max-width: 600px) { .grid { grid-template-columns: 1fr 1fr; gap: 10px; } }
    .card { background: var(--card); border-radius: 15px; overflow: hidden; border: 1px solid #222; transition: 0.3s; text-align: center; }
    .card:hover { border-color: var(--primary); transform: translateY(-5px); }
    .card img { width: 100%; height: 260px; object-fit: cover; }
    
    /* Details Page Lighting */
    .details-box { display: flex; flex-wrap: wrap; gap: 30px; background: #10141d; padding: 30px; border-radius: 20px; border: 1px solid var(--primary); box-shadow: 0 0 30px rgba(0, 242, 255, 0.1); }
    .details-poster { width: 300px; border-radius: 15px; box-shadow: 0 0 20px var(--primary); }
    .info-panel { flex: 1; min-width: 300px; }
    .tag { background: rgba(0, 242, 255, 0.1); color: var(--primary); padding: 5px 12px; border-radius: 5px; border: 1px solid var(--primary); font-size: 12px; margin-right: 5px; }

    /* Admin UI */
    .admin-menu { background: #161b22; padding: 20px; border-radius: 15px; margin-bottom: 25px; border-left: 5px solid var(--primary); }
    input, textarea, select { width: 100%; padding: 12px; margin: 10px 0; background: #0d1117; color: white; border: 1px solid #30363d; border-radius: 8px; }
</style>
"""

# --- রুট: হোমপেজ ---
@app.get("/", response_class=HTMLResponse)
async def home(q: str = Query(None), cat: str = Query(None), ott: str = Query(None)):
    conf = await get_config()
    otts = await ott_col.find().to_list(100)
    cats = await category_col.find().to_list(100)
    
    query = {}
    if q: query["title"] = {"$regex": q, "$options": "i"}
    if cat: query["category"] = cat
    if ott: query["ott_id"] = ott
    
    items = await content_col.find(query).sort("_id", -1).to_list(40)
    
    html = f"<html><head><title>{conf['site_name']}</title><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}{conf['popunder']}</head><body>"
    html += f"<div class='header'><h1 class='neon-text'>⚡ {conf['site_name']}</h1></div>"
    if conf['notice']: html += f"<div class='notice'>📢 {conf['notice']}</div>"
    
    html += "<div class='container'>"
    
    # OTT & Categories
    html += "<div style='display:flex; gap:15px; overflow-x:auto; padding-bottom:15px;'>"
    for o in otts:
        html += f"<a href='/?ott={o['_id']}' style='text-align:center; text-decoration:none; color:white;'><img src='{o['logo']}' style='width:60px; height:60px; border-radius:50%; border:2px solid var(--primary);'><br><small>{o['name']}</small></a>"
    html += "</div>"
    
    html += f"<form style='display:flex; gap:10px;'><input name='q' placeholder='Search movies, series, actors...' value='{q or ''}'><button class='btn'>🔍</button></form>"
    
    # Movie Grid
    html += "<div class='grid'>"
    for i in items:
        poster = i.get('poster') or "https://via.placeholder.com/300x450"
        html += f"""<div class='card'>
            <img src='{poster}'>
            <div style='padding:12px;'>
                <h4 style='margin:5px 0; font-size:14px;'>{i['title']}</h4>
                <a href='/movie/{i['_id']}' class='btn' style='font-size:11px; width:100%; box-sizing:border-box;'>WATCH NOW</a>
            </div>
        </div>"""
    html += "</div></div></body></html>"
    return html

# --- রুট: ডিটেইলস পেজ (সব তথ্যসহ) ---
@app.get("/movie/{id}", response_class=HTMLResponse)
async def details(id: str):
    conf = await get_config()
    item = await content_col.find_one({"_id": ObjectId(id)})
    if not item: return "Content Not Found"
    
    html = f"<html><head><title>{item['title']}</title><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}</head><body>"
    html += f"<div class='header'><h1 class='neon-text'>{conf['site_name']}</h1></div>"
    html += f"<div class='container'><div class='details-box'>"
    
    # Poster & Trailer
    html += "<div>"
    html += f"<img src='{item.get('poster')}' class='details-poster'>"
    if item.get('trailer'):
        html += f"<h3 class='neon-text' style='margin-top:20px;'>🎬 Trailer</h3><iframe width='300' height='180' src='https://www.youtube.com/embed/{item['trailer'].split('v=')[-1]}' frameborder='0' allowfullscreen style='border-radius:10px; border:1px solid var(--primary);'></iframe>"
    html += "</div>"
    
    # Info Panel
    html += "<div class='info-panel'>"
    html += f"<h1 class='neon-text' style='margin-top:0;'>{item['title']}</h1>"
    html += f"<p><span class='tag'>⭐ {item.get('rating', 'N/A')}</span> <span class='tag'>🌐 {item.get('language', 'N/A')}</span> <span class='tag'>💎 {item.get('quality', 'HD')}</span></p>"
    html += f"<p><b>🎭 Actors:</b> {item.get('actors', 'N/A')}</p>"
    html += f"<p style='color:#ccc;'><b>📝 Story:</b> {item.get('description', 'No description available.')}</p>"
    
    # Download Links
    html += "<h2 class='neon-text' style='margin-top:40px;'>🚀 DOWNLOAD LINKS</h2>"
    if item['type'] == 'movie':
        for idx, q in enumerate(item.get('qualities', [])):
            html += f"<div style='margin-bottom:10px;'><a href='/verify/{id}/movie/{idx}/0' class='btn' style='width:100%; text-align:center;'>{q['quality']} - Server Link</a></div>"
    else:
        for s_idx, s in enumerate(item.get('seasons', [])):
            html += f"<h3 style='border-bottom:1px solid var(--primary); padding-bottom:5px;'>Season {s['s_num']}</h3>"
            for e_idx, ep in enumerate(s['episodes']):
                html += f"<div style='margin-bottom:10px;'><b>Ep {ep['e_num']}</b>: "
                for q_idx, q in enumerate(ep['qualities']):
                    html += f"<a href='/verify/{id}/series/{s_idx}_{e_idx}_{q_idx}/0' class='btn' style='padding:5px 12px; font-size:12px; margin-left:5px;'>{q['quality']}</a>"
                html += "</div>"
    
    html += "</div></div>"
    html += "<br><a href='/' class='btn' style='background:#333; box-shadow:none;'>⬅️ BACK TO HOME</a></div></body></html>"
    return html

# --- রুট: অ্যাড ভেরিফিকেশন সিস্টেম ---
@app.get("/verify/{id}/{ctype}/{cidx}/{step}", response_class=HTMLResponse)
async def verify(id: str, ctype: str, cidx: str, step: int):
    conf = await get_config()
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
    <body><div class='container' style='text-align:center; padding-top:100px;'>
    <div class='details-box' style='display:inline-block;'>
        <h2 class='neon-text'>🔓 Step {step+1} of {total}</h2>
        <p>Your link is almost ready! Click continue to verify.</p>
        <a href="{current_ad}" target="_blank" onclick="window.location.href='/verify/{id}/{ctype}/{cidx}/{step+1}'" class='btn' style='font-size:20px;'>CONTINUE ➡️</a>
    </div></div></body></html>"""

# --- রুট: ৩-মেনু অ্যাডমিন প্যানেল (Emojis & Lighting) ---
@app.get("/admin", response_class=HTMLResponse)
async def admin():
    conf = await get_config()
    otts = await ott_col.find().to_list(100)
    cats = await category_col.find().to_list(100)
    
    html = f"<html><head><title>Admin Panel</title>{CSS}</head><body><div class='container'>"
    html += "<h1 class='neon-text'>🛡️ MASTER DASHBOARD</h1>"
    
    # মেনু ১: জেনারেল সেটিংস
    html += f"""<div class='admin-menu'><h3>⚙️ ১. Global Settings</h3>
    <form action='/admin/settings' method='post'>
        <label>Site Name:</label><input name='site_name' value='{conf['site_name']}'>
        <label>Notice Bar:</label><textarea name='notice'>{conf['notice']}</textarea>
        <label>Total Ad Steps:</label><input type='number' name='total_steps' value='{conf['total_steps']}'>
        <label>Ad URLs (Comma Separated):</label><textarea name='ad_urls'>{conf['ad_step_urls']}</textarea>
        <label>Popunder Code:</label><textarea name='popunder'>{conf['popunder']}</textarea>
        <button class='btn'>✅ Update Settings</button>
    </form></div>"""

    # মেনু ২: ওটিটি ও ক্যাটাগরি
    html += """<div class='admin-menu'><h3>📺 ২. Media & Labels</h3>
    <div style='display:grid; grid-template-columns:1fr 1fr; gap:20px;'>
        <div><h4>Add OTT Provider</h4><form action='/admin/add_ott' method='post'><input name='name' placeholder='Name'><input name='logo' placeholder='Logo URL'><button class='btn'>➕ Add</button></form></div>
        <div><h4>Add Category</h4><form action='/admin/add_cat' method='post'><input name='name' placeholder='Category Name'><button class='btn'>➕ Add</button></form></div>
    </div></div>"""

    # মেনু ৩: কন্টেন্ট আপলোডার
    html += f"""<div class='admin-menu'><h3>🎬 ৩. Content Manager</h3>
    <form action='/admin/add_content' method='post'>
        <input name='title' placeholder='Title' required>
        <input name='poster' placeholder='Poster URL'>
        <input name='rating' placeholder='Rating (e.g. 8.4)'>
        <input name='lang' placeholder='Language'>
        <input name='actors' placeholder='Actors Name'>
        <input name='trailer' placeholder='Trailer Link'>
        <input name='quality' placeholder='Quality (4K, BluRay)'>
        <textarea name='desc' placeholder='Description'></textarea>
        <select name='type'><option value='movie'>Movie</option><option value='series'>Series</option></select>
        <select name='cat'>{"".join([f"<option value='{c['name']}'>{c['name']}</option>" for c in cats])}</select>
        <select name='ott'>{"".join([f"<option value='{o['_id']}'>{o['name']}</option>" for o in otts])}</select>
        <textarea name='json' placeholder='JSON Data (Links)'></textarea>
        <button class='btn'>🚀 Publish Now</button>
    </form></div>"""

    html += "</div></body></html>"
    return html

# --- অ্যাডমিন পোস্ট হ্যান্ডলারস ---
@app.post("/admin/settings")
async def save_settings(site_name: str=Form(...), notice: str=Form(...), total_steps: int=Form(...), ad_urls: str=Form(...), popunder: str=Form("")):
    await settings_col.update_one({"type": "global"}, {"$set": {"site_name": site_name, "notice": notice, "total_steps": total_steps, "ad_step_urls": ad_urls, "popunder": popunder}})
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/add_content")
async def add_content(title: str=Form(...), poster: str=Form(...), rating: str=Form(...), lang: str=Form(...), actors: str=Form(...), trailer: str=Form(...), quality: str=Form(...), desc: str=Form(...), type: str=Form(...), cat: str=Form(...), ott: str=Form(...), json: str=Form(...)):
    import json as pyjson
    doc = {"title": title, "poster": poster, "rating": rating, "language": lang, "actors": actors, "trailer": trailer, "quality": quality, "description": desc, "type": type, "category": cat, "ott_id": ott}
    data = pyjson.loads(json)
    if type == 'movie': doc['qualities'] = data
    else: doc['seasons'] = data
    await content_col.insert_one(doc)
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/add_ott")
async def add_ott(name: str=Form(...), logo: str=Form(...)):
    await ott_col.insert_one({"name": name, "logo": logo})
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/add_cat")
async def add_cat(name: str=Form(...)):
    await category_col.insert_one({"name": name})
    return RedirectResponse(url="/admin", status_code=303)

# --- অটো আপলোড টেলিগ্রাম বট ---
@bot.on_message(filters.chat(CHANNEL_ID) & (filters.video | filters.document))
async def auto_post(client, message):
    title = message.caption or "New Upload"
    link = f"https://t.me/c/{str(CHANNEL_ID)[4:]}/{message.id}"
    await content_col.insert_one({
        "title": title, "poster": "", "type": "movie", "category": "General",
        "qualities": [{"quality": "Original File", "link": link}]
    })

@app.on_event("startup")
async def startup(): await bot.start()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
