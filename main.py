import os
import asyncio
import json
from fastapi import FastAPI, Request, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from pyrogram import Client, filters
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import uvicorn

# --- ১. কনফিগারেশন (Render-এর Environment Variables থেকে আসবে) ---
API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")
MONGO_URL = os.getenv("MONGO_URL", "your_mongodb_url")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-100123456789"))
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

# --- ২. ডাটাবেস ও বট ইনিশিয়ালাইজ ---
app = FastAPI()
db_client = AsyncIOMotorClient(MONGO_URL)
db = db_client['cinema_pro_final_v5']
content_col = db['content']
settings_col = db['settings']
category_col = db['categories']
ott_col = db['otts']

# বট ক্লায়েন্ট
bot = Client("movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- ৩. গ্লোবাল সেটিংস হেল্পার ---
async def get_site_conf():
    conf = await settings_col.find_one({"type": "global"})
    if not conf:
        conf = {
            "type": "global", 
            "site_name": "NEON CINEMA PRO", 
            "notice": "Welcome to our premium movie portal! 🎬", 
            "popunder": "", "header_banner": "",
            "ad_step_urls": "", "total_steps": 0
        }
        await settings_col.insert_one(conf)
    return conf

# --- ৪. আল্ট্রা নিয়ন লাইটিং ও আধুনিক CSS ---
CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap');
    :root { --primary: #00f2ff; --secondary: #bc13fe; --bg: #05070a; --card: #10141d; --text: #ffffff; }
    body { font-family: 'Poppins', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 0; overflow-x: hidden; }
    
    /* Neon Glow Effects */
    .neon-text { color: var(--primary); text-shadow: 0 0 10px var(--primary), 0 0 20px var(--primary); }
    .header { background: rgba(16, 20, 29, 0.95); backdrop-filter: blur(15px); padding: 20px; text-align: center; border-bottom: 2px solid var(--primary); position: sticky; top:0; z-index:100; }
    .notice-bar { background: linear-gradient(90deg, var(--primary), var(--secondary)); color: #000; padding: 10px; text-align: center; font-weight: bold; font-size: 14px; box-shadow: 0 0 15px var(--primary); }
    
    .container { max-width: 1200px; margin: auto; padding: 20px; }
    .btn { background: linear-gradient(45deg, var(--primary), var(--secondary)); color: white; padding: 10px 25px; border-radius: 50px; text-decoration: none; font-weight: bold; border: none; cursor: pointer; display: inline-block; transition: 0.3s; box-shadow: 0 0 15px rgba(0, 242, 255, 0.4); }
    .btn:hover { transform: scale(1.05); box-shadow: 0 0 30px var(--primary); }
    
    /* Movie Grid */
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 20px; margin-top: 25px; }
    @media (max-width: 600px) { .grid { grid-template-columns: 1fr 1fr; gap: 10px; } }
    .card { background: var(--card); border-radius: 15px; overflow: hidden; border: 1px solid #222; transition: 0.3s; text-align: center; }
    .card:hover { border-color: var(--primary); transform: translateY(-5px); box-shadow: 0 0 20px rgba(0, 242, 255, 0.2); }
    .card img { width: 100%; height: 280px; object-fit: cover; }
    .card-info { padding: 12px; }

    /* OTT Platform Icons */
    .ott-circle { width: 65px; height: 65px; border-radius: 50%; border: 2px solid var(--primary); object-fit: cover; transition: 0.3s; box-shadow: 0 0 10px rgba(0,242,255,0.3); }
    .ott-circle:hover { transform: scale(1.15); box-shadow: 0 0 20px var(--primary); }

    /* Details Page Lighting */
    .details-box { display: grid; grid-template-columns: 350px 1fr; gap: 30px; background: rgba(255,255,255,0.02); padding: 30px; border-radius: 20px; border: 1px solid var(--primary); box-shadow: 0 0 30px rgba(0, 242, 255, 0.1); }
    @media (max-width: 800px) { .details-box { grid-template-columns: 1fr; } }
    .poster-img { width: 100%; border-radius: 15px; box-shadow: 0 0 25px var(--primary); }
    .badge { background: rgba(0, 242, 255, 0.15); color: var(--primary); padding: 5px 12px; border-radius: 5px; border: 1px solid var(--primary); font-size: 13px; font-weight: bold; margin-right: 8px; }

    /* Admin Panel */
    .admin-card { background: #161b22; padding: 25px; border-radius: 15px; margin-bottom: 25px; border-left: 5px solid var(--primary); }
    input, textarea, select { width: 100%; padding: 12px; margin: 10px 0; background: #0d1117; color: white; border: 1px solid #30363d; border-radius: 8px; }
</style>
"""

# --- ৫. ইউজার প্যানেল রুটস (Home, View, Verify) ---

@app.get("/", response_class=HTMLResponse)
async def homepage(q: str = Query(None), cat: str = Query(None), ott: str = Query(None)):
    conf = await get_site_conf()
    otts = await ott_col.find().to_list(100)
    cats = await category_col.find().to_list(100)
    
    query = {}
    if q: query["title"] = {"$regex": q, "$options": "i"}
    if cat: query["category"] = cat
    if ott: query["ott_id"] = ott
    
    items = await content_col.find(query).sort("_id", -1).to_list(40)
    
    html = f"<html><head><title>{conf['site_name']}</title><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}{conf['popunder']}</head><body>"
    html += f"<div class='header'><h1 class='neon-text'>🚀 {conf['site_name']}</h1></div>"
    if conf['notice']: html += f"<div class='notice-bar'>📢 {conf['notice']}</div>"
    
    html += "<div class='container'>"
    # OTT Platforms
    html += "<div style='display:flex; gap:20px; overflow-x:auto; padding:15px; justify-content: center;'>"
    for o in otts:
        html += f"<a href='/?ott={o['_id']}' style='text-align:center; text-decoration:none; color:white;'><img src='{o['logo']}' class='ott-circle'><br><small style='display:block; margin-top:5px;'>{o['name']}</small></a>"
    html += "</div>"
    
    # Search & Categories
    html += f"<form style='display:flex; gap:10px; margin:20px 0;'><input name='q' placeholder='Search movies, series...' value='{q or ''}'><button class='btn'>🔍 SEARCH</button></form>"
    html += "<div style='text-align:center; margin-bottom:25px;'><a href='/' class='badge' style='background:gray; color:white; border:none;'>ALL</a>"
    for c in cats:
        html += f"<a href='/?cat={c['name']}' class='badge'>{c['name']}</a>"
    html += "</div>"

    # Grid
    html += "<div class='grid'>"
    for i in items:
        poster = i.get('poster') or "https://via.placeholder.com/300x450"
        html += f"""<div class='card'>
            <img src='{poster}'>
            <div class='card-info'>
                <h4 style='font-size:14px; height:40px; overflow:hidden;'>{i['title']}</h4>
                <a href='/movie/{i['_id']}' class='btn' style='font-size:12px; width:100%; box-sizing:border-box;'>WATCH NOW</a>
            </div>
        </div>"""
    html += "</div></div></body></html>"
    return html

@app.get("/movie/{id}", response_class=HTMLResponse)
async def movie_details(id: str):
    conf = await get_site_conf()
    item = await content_col.find_one({"_id": ObjectId(id)})
    if not item: return "Error: Content Not Found"
    
    html = f"<html><head><title>{item['title']}</title><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}</head><body>"
    html += f"<div class='header'><h1 class='neon-text'>{conf['site_name']}</h1></div>"
    html += f"<div class='container'><div class='details-box'><div>"
    html += f"<img src='{item.get('poster')}' class='poster-img'>"
    if item.get('trailer'):
        yt_id = item['trailer'].split('v=')[-1].split('&')[0]
        html += f"<h3 class='neon-text' style='margin-top:25px;'>🎬 WATCH TRAILER</h3><iframe width='100%' height='200' src='https://www.youtube.com/embed/{yt_id}' frameborder='0' allowfullscreen style='border-radius:15px; border:1px solid var(--primary);'></iframe>"
    html += f"</div><div><h1 class='neon-text' style='margin-top:0;'>{item['title']}</h1>"
    html += f"<p><span class='badge'>⭐ {item.get('rating', 'N/A')}</span> <span class='badge'>🌐 {item.get('language', 'N/A')}</span> <span class='badge'>💎 {item.get('quality', 'HD')}</span></p>"
    html += f"<p><b>🎭 CAST:</b> {item.get('actors', 'N/A')}</p><p style='color:#ccc; line-height:1.6;'><b>📝 STORY:</b> {item.get('description', 'No description available.')}</p>"
    
    html += "<h2 class='neon-text' style='margin-top:40px;'>📥 DOWNLOAD & STREAM</h2>"
    if item['type'] == 'movie':
        for idx, q in enumerate(item.get('qualities', [])):
            html += f"<div style='margin-bottom:12px;'><a href='/verify/{id}/movie/{idx}/0' class='btn' style='width:100%; text-align:center;'>{q['quality']} - SECURE SERVER</a></div>"
    else:
        for s_idx, s in enumerate(item.get('seasons', [])):
            html += f"<h3 style='border-bottom:2px solid var(--primary); padding-bottom:5px;'>SEASON {s['s_num']}</h3>"
            for e_idx, ep in enumerate(s['episodes']):
                html += f"<div style='background:#1a1f2b; padding:15px; border-radius:12px; margin-bottom:12px;'><b>EPISODE {ep['e_num']}</b>: "
                for q_idx, q in enumerate(ep['qualities']):
                    html += f"<a href='/verify/{id}/series/{s_idx}_{e_idx}_{q_idx}/0' class='btn' style='padding:5px 12px; font-size:12px; margin-left:8px;'>{q['quality']}</a>"
                html += "</div>"
    
    html += "</div></div><br><a href='/' class='btn' style='background:#222; box-shadow:none;'>⬅️ BACK TO HOME</a></div></body></html>"
    return html

@app.get("/verify/{id}/{ctype}/{cidx}/{step}", response_class=HTMLResponse)
async def verify_process(id: str, ctype: str, cidx: str, step: int):
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

    current_ad = urls[step].strip() if step < len(urls) else "#"
    return f"""<html><head><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}</head>
    <body style='display:flex; align-items:center; justify-content:center; height:100vh; text-align:center;'>
    <div class='container'><div class='admin-card' style='display:inline-block; max-width:500px;'>
        <h2 class='neon-text'>🔐 STEP {step+1} of {total}</h2>
        <p>Unlock your final link by clicking the button below.</p>
        <div style='margin:25px 0;'>{conf['header_banner']}</div>
        <a href="{current_ad}" target="_blank" onclick="window.location.href='/verify/{id}/{ctype}/{cidx}/{step+1}'" class='btn' style='font-size:22px;'>CONTINUE TO NEXT STEP ➡️</a>
    </div></div></body></html>"""

# --- ৬. প্রফেশনাল ৩-মেনু অ্যাডমিন প্যানেল ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(passkey: str = Query(None)):
    if passkey != ADMIN_PASS: return "<h1>🚫 Access Denied!</h1>"
    conf = await get_site_conf()
    otts = await ott_col.find().to_list(100)
    cats = await category_col.find().to_list(100)
    contents = await content_col.find().sort("_id", -1).to_list(15)
    
    html = f"<html><head><title>Admin Dashboard</title>{CSS}</head><body><div class='container'>"
    html += "<h1 class='neon-text'>🛡️ MASTER DASHBOARD</h1>"
    
    # মেনু ১: জেনারেল সেটিংস
    html += f"""<div class='admin-card'><h3>⚙️ ১. Global Configuration</h3>
    <form action='/admin/save_global' method='post'><input type='hidden' name='pass' value='{ADMIN_PASS}'>
        <label>🌐 Site Name:</label><input name='site_name' value='{conf['site_name']}'>
        <label>📢 Notice Bar:</label><textarea name='notice'>{conf['notice']}</textarea>
        <label>🔢 Total Ad Steps:</label><input type='number' name='total_steps' value='{conf['total_steps']}'>
        <label>🔗 Ad URLs (Comma Separated):</label><textarea name='ad_urls' rows='3'>{conf['ad_step_urls']}</textarea>
        <label>🖼️ Popunder/Banner Script:</label><textarea name='popunder' rows='3'>{conf['popunder']}</textarea>
        <button class='btn'>✅ UPDATE SETTINGS</button>
    </form></div>"""

    # মেনু ২: ওটিটি ও ক্যাটাগরি
    html += f"""<div class='admin-card'><h3>📺 ২. Taxonomy & Media</h3>
    <div style='display:grid; grid-template-columns: 1fr 1fr; gap:25px;'>
        <div>
            <h4>➕ Add OTT Provider</h4>
            <form action='/admin/add_ott' method='post'><input type='hidden' name='pass' value='{ADMIN_PASS}'><input name='n' placeholder='Netflix'><input name='l' placeholder='Logo URL'><button class='btn'>ADD</button></form>
            <div style='margin-top:10px;'>""" + "".join([f"<p>🔹 {o['name']} <a href='/admin/del_ott/{o['_id']}?pass={ADMIN_PASS}' style='color:red;'>[X]</a></p>" for o in otts]) + """</div>
        </div>
        <div>
            <h4>➕ Add Category</h4>
            <form action='/admin/add_cat' method='post'><input type='hidden' name='pass' value='{ADMIN_PASS}'><input name='n' placeholder='Action'><button class='btn'>ADD</button></form>
            <div style='margin-top:10px;'>""" + "".join([f"<p>🔸 {c['name']} <a href='/admin/del_cat/{c['_id']}?pass={ADMIN_PASS}' style='color:red;'>[X]</a></p>" for c in cats]) + """</div>
        </div>
    </div></div>"""

    # মেনু ৩: কন্টেন্ট ম্যানেজার
    html += f"""<div class='admin-card'><h3>🎬 ৩. Content Management</h3>
    <form action='/admin/add_content' method='post'><input type='hidden' name='pass' value='{ADMIN_PASS}'>
        <div style='display:grid; grid-template-columns:1fr 1fr; gap:12px;'>
            <input name='title' placeholder='Movie Title' required><input name='poster' placeholder='Poster URL'>
            <input name='rating' placeholder='Rating (8.5)'><input name='lang' placeholder='Language'>
            <input name='actors' placeholder='Actors Name'><input name='trailer' placeholder='Trailer URL'>
            <input name='quality' placeholder='Quality (4K)'>
            <select name='type'><option value='movie'>Movie</option><option value='series'>Series</option></select>
            <select name='cat'><option value=''>Select Category</option>{"".join([f"<option value='{c['name']}'>{c['name']}</option>" for c in cats])}</select>
            <select name='ott'><option value=''>Select OTT Provider</option>{"".join([f"<option value='{o['_id']}'>{o['name']}</option>" for o in otts])}</select>
        </div>
        <textarea name='desc' placeholder='Short Description'></textarea>
        <textarea name='json' rows='4' placeholder='JSON Quality Links: [{"quality":"720p","link":"url"}]'></textarea>
        <button class='btn'>🚀 PUBLISH NOW</button>
    </form>
    <hr style='border:1px solid #333; margin:25px 0;'>
    <h4>🗑️ Recent Content (Delete)</h4>
    {"".join([f"<p>🎥 {c['title']} <a href='/admin/del_con/{c['_id']}?pass={ADMIN_PASS}' style='color:red; margin-left:10px;'>[Delete]</a></p>" for c in contents])}
    </div>"""

    # বট ম্যানুয়াল কন্ট্রোল বাটন
    html += f"<div class='admin-card'><h3>🤖 Bot Control</h3><a href='/admin/restart_bot?pass={ADMIN_PASS}' class='btn'>START / RESTART BOT</a></div>"
    
    html += "</div><div style='text-align:center; padding:20px;'><a href='/' class='btn' style='background:gray;'>⬅️ BACK TO HOMEPAGE</a></div></body></html>"
    return html

# --- ৭. অ্যাডমিন অ্যাকশন হ্যান্ডলারস (POST/GET) ---

@app.post("/admin/save_global")
async def admin_save_global(pass_key: str=Form(None, alias="pass"), site_name: str=Form(...), notice: str=Form(...), total_steps: int=Form(...), ad_urls: str=Form(...), popunder: str=Form("")):
    if pass_key != ADMIN_PASS: return "Unauthorized"
    await settings_col.update_one({"type": "global"}, {"$set": {"site_name": site_name, "notice": notice, "total_steps": total_steps, "ad_step_urls": ad_urls, "popunder": popunder}}, upsert=True)
    return RedirectResponse(url=f"/admin?passkey={ADMIN_PASS}", status_code=303)

@app.post("/admin/add_content")
async def admin_add_content(pass_key: str=Form(None, alias="pass"), title: str=Form(...), poster: str=Form(...), rating: str=Form(...), lang: str=Form(...), actors: str=Form(...), trailer: str=Form(...), quality: str=Form(...), desc: str=Form(...), type: str=Form(...), cat: str=Form(...), ott: str=Form(...), json_data: str=Form(None, alias="json")):
    if pass_key != ADMIN_PASS: return "Unauthorized"
    import json as pyjson
    data = pyjson.loads(json_data) if json_data else []
    doc = {"title": title, "poster": poster, "rating": rating, "language": lang, "actors": actors, "trailer": trailer, "quality": quality, "description": desc, "type": type, "category": cat, "ott_id": ott}
    if type == 'movie': doc['qualities'] = data
    else: doc['seasons'] = data
    await content_col.insert_one(doc)
    return RedirectResponse(url=f"/admin?passkey={ADMIN_PASS}", status_code=303)

@app.post("/admin/add_ott")
async def admin_add_ott(pass_key: str=Form(None, alias="pass"), n: str=Form(...), l: str=Form(...)):
    if pass_key != ADMIN_PASS: return "Unauthorized"
    await ott_col.insert_one({"name": n, "logo": l})
    return RedirectResponse(url=f"/admin?passkey={ADMIN_PASS}", status_code=303)

@app.post("/admin/add_cat")
async def admin_add_cat(pass_key: str=Form(None, alias="pass"), n: str=Form(...)):
    if pass_key != ADMIN_PASS: return "Unauthorized"
    await category_col.insert_one({"name": n})
    return RedirectResponse(url=f"/admin?passkey={ADMIN_PASS}", status_code=303)

@app.get("/admin/del_ott/{id}")
async def admin_del_ott(id: str, pass_key: str = Query(None, alias="pass")):
    if pass_key != ADMIN_PASS: return "Unauthorized"
    await ott_col.delete_one({"_id": ObjectId(id)})
    return RedirectResponse(url=f"/admin?passkey={ADMIN_PASS}", status_code=303)

@app.get("/admin/del_cat/{id}")
async def admin_del_cat(id: str, pass_key: str = Query(None, alias="pass")):
    if pass_key != ADMIN_PASS: return "Unauthorized"
    await category_col.delete_one({"_id": ObjectId(id)})
    return RedirectResponse(url=f"/admin?passkey={ADMIN_PASS}", status_code=303)

@app.get("/admin/del_con/{id}")
async def admin_del_con(id: str, pass_key: str = Query(None, alias="pass")):
    if pass_key != ADMIN_PASS: return "Unauthorized"
    await content_col.delete_one({"_id": ObjectId(id)})
    return RedirectResponse(url=f"/admin?passkey={ADMIN_PASS}", status_code=303)

@app.get("/admin/restart_bot")
async def admin_restart_bot(pass_key: str = Query(None, alias="pass")):
    if pass_key != ADMIN_PASS: return "Unauthorized"
    if bot.is_connected:
        await bot.stop()
    asyncio.create_task(bot.start())
    return RedirectResponse(url=f"/admin?passkey={ADMIN_PASS}", status_code=303)

# --- ৮. টেলিগ্রাম বট ও সার্ভার রান ---

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
    # বটটিকে ব্যাকগ্রাউন্ডে স্টার্ট করা হচ্ছে যেন ওয়েব সার্ভার ব্লক না হয়
    asyncio.create_task(bot.start())

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
