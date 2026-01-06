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

# --- এনভায়রনমেন্ট ভেরিয়েবলস ---
API_ID = int(os.getenv("API_ID", "12345"))
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")
MONGO_URL = os.getenv("MONGO_URL", "your_mongodb_url")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-100123456789"))
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

# --- ডাটাবেস সেটিংস (Connection Timeout ফিক্সড) ---
app = FastAPI()
db_client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
db = db_client['cinema_master_final']
content_col = db['content']
settings_col = db['settings']
category_col = db['categories']
ott_col = db['otts']

# টেলিগ্রাম বট
bot = Client("movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- ১. সেটিংস হেল্পার (যাতে Internal Server Error না আসে) ---
async def get_site_conf():
    try:
        conf = await settings_col.find_one({"type": "global"})
        if not conf:
            conf = {
                "type": "global", "site_name": "NEON CINEMA PRO", 
                "notice": "Welcome to our portal! 🎬", "popunder": "", 
                "ad_step_urls": "", "total_steps": 0
            }
            await settings_col.insert_one(conf)
        return conf
    except Exception:
        # ডাটাবেস কানেক্ট না হলে ডিফল্ট ডেটা পাঠাবে যাতে সাইট ক্রাশ না করে
        return {"site_name": "NEON CINEMA", "notice": "Database Connecting...", "total_steps": 0, "popunder": "", "ad_step_urls": ""}

# --- ২. নিয়ন লাইটিং CSS ---
CSS = """
<style>
    :root { --primary: #00f2ff; --secondary: #bc13fe; --bg: #05070a; --card: #10141d; --text: #fff; }
    body { font-family: sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 0; }
    .header { background: #10141d; padding: 20px; text-align: center; border-bottom: 2px solid var(--primary); box-shadow: 0 0 15px var(--primary); }
    .neon-text { color: var(--primary); text-shadow: 0 0 10px var(--primary); }
    .notice { background: linear-gradient(90deg, var(--primary), var(--secondary)); color: #000; padding: 10px; text-align: center; font-weight: bold; }
    .container { max-width: 1100px; margin: auto; padding: 20px; }
    .btn { background: linear-gradient(45deg, var(--primary), var(--secondary)); color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; font-weight: bold; border: none; cursor: pointer; display: inline-block; transition: 0.3s; }
    .btn:hover { transform: scale(1.05); box-shadow: 0 0 20px var(--primary); }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; }
    @media (max-width: 600px) { .grid { grid-template-columns: 1fr 1fr; gap: 10px; } }
    .card { background: var(--card); border-radius: 10px; overflow: hidden; border: 1px solid #222; text-align: center; }
    .card img { width: 100%; height: 250px; object-fit: cover; }
    .details-box { display: grid; grid-template-columns: 320px 1fr; gap: 30px; background: #10141d; padding: 20px; border-radius: 15px; border: 1px solid var(--primary); }
    @media (max-width: 800px) { .details-box { grid-template-columns: 1fr; } }
    input, textarea, select { width: 100%; padding: 12px; margin: 10px 0; background: #000; color: #fff; border: 1px solid #333; border-radius: 5px; }
    .badge { background: rgba(0,242,255,0.1); color: var(--primary); padding: 4px 8px; border-radius: 4px; border: 1px solid var(--primary); font-size: 11px; margin-right: 5px; }
</style>
"""

# --- ৩. ইউজার প্যানেল রুটস ---

@app.get("/", response_class=HTMLResponse)
async def home(q: str = Query(None), cat: str = Query(None)):
    conf = await get_site_conf()
    try:
        cats = await category_col.find().to_list(100)
        query = {"title": {"$regex": q, "$options": "i"}} if q else {}
        if cat: query["category"] = cat
        items = await content_col.find(query).sort("_id", -1).to_list(40)
    except Exception:
        return "<h1>MongoDB Error!</h1><p>Whitelist IP 0.0.0.0/0 in MongoDB Atlas settings.</p>"
    
    html = f"<html><head><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}{conf.get('popunder','')}</head><body>"
    html += f"<div class='header'><h1 class='neon-text'>{conf['site_name']}</h1></div>"
    if conf['notice']: html += f"<div class='notice'>{conf['notice']}</div>"
    html += f"<div class='container'><form style='display:flex;gap:10px;margin-bottom:20px'><input name='q' placeholder='Search...' value='{q or ''}'><button class='btn'>Search</button></form>"
    html += "<div style='margin-bottom:20px;'>"
    for c in cats: html += f"<a href='/?cat={c['name']}' class='badge' style='text-decoration:none'>{c['name']}</a>"
    html += "</div><div class='grid'>"
    for i in items:
        p = i.get('poster') or "https://via.placeholder.com/300"
        html += f"<div class='card'><img src='{p}'><div style='padding:10px;'><h4>{i['title']}</h4><a href='/movie/{i['_id']}' class='btn' style='font-size:12px;width:100%'>WATCH NOW</a></div></div>"
    html += "</div></div></body></html>"
    return html

@app.get("/movie/{id}", response_class=HTMLResponse)
async def movie_details(id: str):
    try:
        item = await content_col.find_one({"_id": ObjectId(id)})
    except: return "Invalid ID"
    
    if not item: return "Not Found"
    html = f"<html><head><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}</head><body>"
    html += f"<div class='container'><div class='details-box'><div><img src='{item.get('poster')}' style='width:100%;border-radius:10px'>"
    if item.get('trailer'):
        tid = item['trailer'].split('v=')[-1]
        html += f"<h3 class='neon-text'>Trailer</h3><iframe width='100%' height='200' src='https://www.youtube.com/embed/{tid}' frameborder='0' allowfullscreen></iframe>"
    html += f"</div><div><h1 class='neon-text'>{item['title']}</h1><p><span class='badge'>⭐ {item.get('rating')}</span> <span class='badge'>{item.get('language')}</span> <span class='badge'>{item.get('quality')}</span></p>"
    html += f"<p><b>Cast:</b> {item.get('actors')}</p><p><b>Story:</b> {item.get('description')}</p><h3>Links:</h3>"
    
    if item['type'] == 'movie':
        for idx, q in enumerate(item.get('qualities', [])):
            html += f"<a href='/verify/{id}/movie/{idx}/0' class='btn' style='margin-bottom:10px;display:block;text-align:center;'>{q['quality']} - Server</a>"
    else:
        for s_idx, s in enumerate(item.get('seasons', [])):
            html += f"<h4>Season {s['s_num']}</h4>"
            for e_idx, ep in enumerate(s['episodes']):
                html += f"<div style='margin-bottom:5px;'>Ep {ep['e_num']}: "
                for q_idx, q in enumerate(ep['qualities']):
                    html += f"<a href='/verify/{id}/series/{s_idx}_{e_idx}_{q_idx}/0' class='badge' style='text-decoration:none'>{q['quality']}</a>"
                html += "</div>"
    html += "</div></div><br><a href='/' class='btn' style='background:#333'>Back</a></div></body></html>"
    return html

# --- ভেরিফিকেশন সিস্টেম (Ad-Step) ---
@app.get("/verify/{id}/{ctype}/{cidx}/{step}", response_class=HTMLResponse)
async def verify_page(id: str, ctype: str, cidx: str, step: int):
    conf = await get_site_conf()
    total = int(conf.get('total_steps', 0))
    urls = conf.get('ad_step_urls', "").split(",") if conf.get('ad_step_urls') else []
    
    if step >= total:
        item = await content_col.find_one({"_id": ObjectId(id)})
        if ctype == 'movie': final = item['qualities'][int(cidx)]['link']
        else:
            s_i, e_i, q_i = map(int, cidx.split("_"))
            final = item['seasons'][s_i]['episodes'][e_i]['qualities'][q_i]['link']
        return RedirectResponse(url=final)
    
    curr_ad = urls[step].strip() if step < len(urls) else "#"
    return f"<html><head>{CSS}</head><body style='text-align:center;padding-top:100px;'><div class='container'><div class='details-box' style='display:inline-block'><h2>Step {step+1}/{total}</h2><a href='{curr_ad}' target='_blank' onclick=\"window.location.href='/verify/{id}/{ctype}/{cidx}/{step+1}'\" class='btn'>Continue</a></div></div></body></html>"

# --- ৪. অ্যাডমিন লগইন ও ড্যাশবোর্ড ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    auth = request.cookies.get("admin_auth")
    if auth != ADMIN_PASS:
        return f"<html><head>{CSS}</head><body><div class='container' style='max-width:400px;margin-top:100px'><h1>🔐 Admin Login</h1><form action='/admin/login' method='post'>Password: <input type='password' name='password'><button class='btn' style='width:100%'>Login</button></form></div></body></html>"
    
    conf = await get_site_conf()
    otts = await ott_col.find().to_list(100)
    cats = await category_col.find().to_list(100)
    contents = await content_col.find().sort("_id", -1).to_list(15)
    
    html = f"<html><head><title>Admin Dashboard</title>{CSS}</head><body><div class='container'><h1 class='neon-text'>🛡️ Master Admin</h1>"
    # ১. সেটিংস
    html += f"<div class='admin-box' style='background:#161b22;padding:20px;border-radius:10px;margin-bottom:20px'><h3>⚙️ ১. Settings</h3><form action='/admin/save_settings' method='post'>Site Name: <input name='site_name' value='{conf['site_name']}'>Notice: <textarea name='notice'>{conf['notice']}</textarea>Ad Steps: <input type='number' name='total_steps' value='{conf['total_steps']}'>Ad URLs (Comma): <textarea name='ad_urls' rows='3'>{conf['ad_step_urls']}</textarea><button class='btn'>Save Settings</button></form></div>"
    # ২. কন্টেন্ট
    html += f"<div class='admin-box' style='background:#161b22;padding:20px;border-radius:10px;margin-bottom:20px'><h3>🎬 ২. Content Management</h3><form action='/admin/add_content' method='post'><input name='title' placeholder='Title' required><input name='poster' placeholder='Poster URL'><input name='rating' placeholder='Rating'><input name='lang' placeholder='Lang'><input name='actors' placeholder='Actors'><input name='trailer' placeholder='Trailer URL'><input name='quality' placeholder='Quality'><textarea name='desc' placeholder='Description'></textarea><select name='type'><option value='movie'>Movie</option><option value='series'>Series</option></select><select name='cat'>{''.join([f'<option value=\"{c[\"name\"]}\">{c[\"name\"]}</option>' for c in cats])}</select>JSON: <textarea name='json' rows='3' placeholder='[{\"quality\":\"720p\",\"link\":\"url\"}]'></textarea><button class='btn'>Publish</button></form></div>"
    # ৩. ট্যাক্সোনোমি
    html += f"<div class='admin-box' style='background:#161b22;padding:20px;border-radius:10px'><h3>📂 ৩. Add Category</h3><form action='/admin/add_cat' method='post'><input name='name' placeholder='Category Name'><button class='btn'>Add</button></form></div>"
    
    html += "<h3>Manage Content:</h3>"
    for c in contents: html += f"<p>🎥 {c['title']} <a href='/admin/del_con/{c['_id']}' style='color:red;margin-left:10px'>[Delete]</a></p>"
    html += "</div></body></html>"
    return html

@app.post("/admin/login")
async def admin_login(password: str = Form(...)):
    if password == ADMIN_PASS:
        response = RedirectResponse(url="/admin", status_code=303)
        response.set_cookie(key="admin_auth", value=password)
        return response
    return "<h1>Wrong Password!</h1><a href='/admin'>Try Again</a>"

@app.post("/admin/save_settings")
async def save_settings(request: Request, site_name: str=Form(...), notice: str=Form(...), total_steps: int=Form(...), ad_urls: str=Form(...)):
    if request.cookies.get("admin_auth") != ADMIN_PASS: return "Unauthorized"
    await settings_col.update_one({"type": "global"}, {"$set": {"site_name": site_name, "notice": notice, "total_steps": total_steps, "ad_step_urls": ad_urls}}, upsert=True)
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/add_content")
async def add_content(request: Request, title: str=Form(...), poster: str=Form(...), rating: str=Form(...), lang: str=Form(...), actors: str=Form(...), trailer: str=Form(...), quality: str=Form(...), desc: str=Form(...), type: str=Form(...), cat: str=Form(...), json: str=Form(...)):
    if request.cookies.get("admin_auth") != ADMIN_PASS: return "Unauthorized"
    import json as pyjson
    try: data = pyjson.loads(json)
    except: data = []
    doc = {"title": title, "poster": poster, "rating": rating, "language": lang, "actors": actors, "trailer": trailer, "quality": quality, "description": desc, "type": type, "category": cat}
    if type == 'movie': doc['qualities'] = data
    else: doc['seasons'] = data
    await content_col.insert_one(doc)
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/add_cat")
async def add_cat(request: Request, name: str=Form(...)):
    if request.cookies.get("admin_auth") != ADMIN_PASS: return "Unauthorized"
    await category_col.insert_one({"name": name})
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/admin/del_con/{id}")
async def del_con(request: Request, id: str):
    if request.cookies.get("admin_auth") != ADMIN_PASS: return "Unauthorized"
    await content_col.delete_one({"_id": ObjectId(id)})
    return RedirectResponse(url="/admin", status_code=303)

# --- বট ইভেন্ট ---
@bot.on_message(filters.chat(CHANNEL_ID) & (filters.video | filters.document))
async def auto_post(client, message):
    try:
        title = message.caption or "Auto Update"
        link = f"https://t.me/c/{str(CHANNEL_ID)[4:]}/{message.id}"
        await content_col.insert_one({"title": title, "type": "movie", "qualities": [{"quality": "Original", "link": link}]})
    except: pass

@app.on_event("startup")
async def startup():
    asyncio.create_task(bot.start())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
