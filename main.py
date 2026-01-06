import os
import asyncio
import json
from fastapi import FastAPI, Request, Form, Query, HTTPException
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

# --- ডাটাবেস সেটআপ ---
app = FastAPI()
db_client = AsyncIOMotorClient(MONGO_URL)
db = db_client['cinema_ultimate_final']
content_col = db['content']
settings_col = db['settings']
category_col = db['categories']
ott_col = db['otts']

# --- টেলিগ্রাম বট ইনিশিয়ালাইজ ---
bot = Client("movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# --- সেটিংস লোড করার ফাংশন ---
async def get_site_config():
    try:
        conf = await settings_col.find_one({"type": "global"})
        if not conf:
            conf = {
                "type": "global",
                "site_name": "NEON MOVIE PORTAL",
                "notice": "Welcome! Search and enjoy.",
                "popunder": "",
                "ad_step_urls": "",
                "total_steps": 0
            }
            await settings_col.insert_one(conf)
        return conf
    except Exception:
        return {"site_name": "Error Loading", "notice": "", "total_steps": 0, "ad_step_urls": "", "popunder": ""}

# --- নিয়ন লাইটিং ও আধুনিক CSS ---
CSS = """
<style>
    :root { --primary: #00f2ff; --secondary: #bc13fe; --bg: #050a10; --card: #111827; --text: #ffffff; }
    body { font-family: 'Poppins', sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 0; }
    .neon-text { color: var(--primary); text-shadow: 0 0 10px var(--primary), 0 0 20px var(--primary); }
    .header { background: rgba(17, 24, 39, 0.9); backdrop-filter: blur(15px); padding: 20px; text-align: center; border-bottom: 2px solid var(--primary); position: sticky; top:0; z-index:100; }
    .notice { background: linear-gradient(90deg, var(--primary), var(--secondary)); color: #000; padding: 10px; text-align: center; font-weight: bold; font-size: 14px; }
    .container { max-width: 1200px; margin: auto; padding: 20px; }
    .btn { background: linear-gradient(45deg, var(--primary), var(--secondary)); color: white; padding: 10px 25px; border-radius: 50px; text-decoration: none; font-weight: bold; border: none; cursor: pointer; display: inline-block; transition: 0.3s; box-shadow: 0 0 15px rgba(0, 242, 255, 0.4); }
    .btn:hover { transform: scale(1.05); box-shadow: 0 0 25px var(--primary); }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 20px; margin-top: 20px; }
    @media (max-width: 600px) { .grid { grid-template-columns: 1fr 1fr; gap: 10px; } }
    .card { background: var(--card); border-radius: 15px; overflow: hidden; border: 1px solid #222; transition: 0.3s; text-align: center; }
    .card img { width: 100%; height: 260px; object-fit: cover; }
    .badge { background: rgba(0, 242, 255, 0.1); color: var(--primary); padding: 5px 12px; border-radius: 5px; border: 1px solid var(--primary); font-size: 12px; font-weight: bold; margin-right: 5px; }
    .admin-card { background: #161b22; padding: 25px; border-radius: 15px; margin-bottom: 25px; border-left: 5px solid var(--primary); }
    input, textarea, select { width: 100%; padding: 12px; margin: 10px 0; background: #0d1117; color: white; border: 1px solid #30363d; border-radius: 8px; }
</style>
"""

# --- ১. হোমপেজ ---
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
    
    # OTT Slider
    html += "<div style='display:flex; gap:15px; overflow-x:auto; padding:10px; justify-content:center;'>"
    for o in otts:
        html += f"<a href='/?ott={o['_id']}' style='text-align:center; text-decoration:none; color:white;'><img src='{o['logo']}' style='width:60px; height:60px; border-radius:50%; border:2px solid var(--primary);'><br><small>{o['name']}</small></a>"
    html += "</div>"
    
    html += f"<form style='display:flex; gap:10px; margin:20px 0;'><input name='q' placeholder='Search...' value='{q or ''}'><button class='btn'>🔍</button></form>"
    
    html += "<div class='grid'>"
    for i in items:
        p = i.get('poster') or "https://via.placeholder.com/300"
        html += f"<div class='card'><img src='{p}'><div style='padding:12px;'><h4>{i['title']}</h4><a href='/movie/{i['_id']}' class='btn' style='font-size:12px; width:100%; box-sizing:border-box;'>WATCH NOW</a></div></div>"
    html += "</div></div></body></html>"
    return html

# --- ২. মুভি ডিটেইলস ---
@app.get("/movie/{id}", response_class=HTMLResponse)
async def movie_details(id: str):
    conf = await get_site_config()
    item = await content_col.find_one({"_id": ObjectId(id)})
    if not item: return "Not Found"
    
    html = f"<html><head><title>{item['title']}</title><meta name='viewport' content='width=device-width, initial-scale=1.0'>{CSS}</head><body>"
    html += f"<div class='header'><h1 class='neon-text'>{conf['site_name']}</h1></div>"
    html += f"<div class='container'><div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap:30px;'><div>"
    html += f"<img src='{item.get('poster')}' style='width:100%; border-radius:15px; box-shadow:0 0 20px var(--primary);'>"
    if item.get('trailer'):
        yt_id = item['trailer'].split('v=')[-1]
        html += f"<h3 class='neon-text'>🎬 Trailer</h3><iframe width='100%' height='215' src='https://www.youtube.com/embed/{yt_id}' frameborder='0' allowfullscreen></iframe>"
    html += f"</div><div><h1 class='neon-text'>{item['title']}</h1>"
    html += f"<p><span class='badge'>⭐ {item.get('rating')}</span> <span class='badge'>🌐 {item.get('language')}</span></p>"
    html += f"<p><b>🎭 Cast:</b> {item.get('actors')}</p><p style='color:#ccc;'><b>📝 Story:</b> {item.get('description')}</p>"
    
    html += "<h2 class='neon-text'>📥 DOWNLOAD LINKS</h2>"
    if item['type'] == 'movie':
        for idx, q in enumerate(item.get('qualities', [])):
            html += f"<div style='margin-bottom:10px;'><a href='/verify/{id}/movie/{idx}/0' class='btn' style='width:100%; text-align:center;'>{q['quality']} - Link</a></div>"
    else:
        for s_idx, s in enumerate(item.get('seasons', [])):
            html += f"<h3>Season {s['s_num']}</h3>"
            for e_idx, ep in enumerate(s['episodes']):
                html += f"<div style='margin-bottom:10px;'><b>Ep {ep['e_num']}</b>: "
                for q_idx, q in enumerate(ep['qualities']):
                    html += f"<a href='/verify/{id}/series/{s_idx}_{e_idx}_{q_idx}/0' class='btn' style='padding:5px 10px; font-size:12px;'>{q['quality']}</a>"
                html += "</div>"
    html += "</div></div><br><a href='/' class='btn' style='background:#333;'>⬅️ BACK</a></div></body></html>"
    return html

# --- ৩. অ্যাড ভেরিফিকেশন ---
@app.get("/verify/{id}/{ctype}/{cidx}/{step}", response_class=HTMLResponse)
async def verify(id: str, ctype: str, cidx: str, step: int):
    conf = await get_site_config()
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
    return f"<html><head>{CSS}</head><body style='text-align:center; padding-top:100px;'><div class='container'><div class='admin-card' style='display:inline-block;'><h2>Step {step+1}/{total}</h2><a href='{cur_url}' target='_blank' onclick=\"window.location.href='/verify/{id}/{ctype}/{cidx}/{step+1}'\" class='btn'>CONTINUE ➡️</a></div></div></body></html>"

# --- ৪. অ্যাডমিন প্যানেল (৩-মেনু ও বট স্টার্ট বাটন) ---
@app.get("/admin", response_class=HTMLResponse)
async def admin(passkey: str = Query(None)):
    if passkey != ADMIN_PASS: return "<h1>Access Denied</h1>"
    conf = await get_site_config()
    otts = await ott_col.find().to_list(100)
    cats = await category_col.find().to_list(100)
    
    html = f"<html><head><title>Admin</title>{CSS}</head><body><div class='container'><h1 class='neon-text'>🛡️ MASTER DASHBOARD</h1>"
    
    # বট স্ট্যাটাস ও ম্যানুয়াল স্টার্ট
    bot_status = "✅ Online" if bot.is_connected else "❌ Offline"
    html += f"<div class='admin-card'><h3>🤖 Bot Status: {bot_status}</h3><a href='/admin/start_bot?passkey={ADMIN_PASS}' class='btn'>Restart/Start Bot Manually</a></div>"
    
    # মেনু ১: সেটিংস
    html += f"<div class='admin-card'><h3>⚙️ ১. Settings</h3><form action='/admin/settings' method='post'><input type='hidden' name='passkey' value='{ADMIN_PASS}'>Site Name: <input name='site_name' value='{conf['site_name']}'>Notice: <textarea name='notice'>{conf['notice']}</textarea>Ad Steps: <input type='number' name='total_steps' value='{conf['total_steps']}'>Ad URLs (Comma): <textarea name='ad_urls'>{conf['ad_step_urls']}</textarea>Popunder: <textarea name='popunder'>{conf['popunder']}</textarea><button class='btn'>Save Settings</button></form></div>"
    
    # মেনু ২: ওটিটি ও ক্যাটাগরি
    html += f"<div class='admin-card'><h3>📺 ২. Media</h3><div style='display:grid; grid-template-columns:1fr 1fr; gap:20px;'><div><h4>OTT</h4><form action='/admin/add_ott' method='post'><input type='hidden' name='passkey' value='{ADMIN_PASS}'><input name='name' placeholder='Netflix'><input name='logo' placeholder='Logo URL'><button class='btn'>Add</button></form></div><div><h4>Category</h4><form action='/admin/add_cat' method='post'><input type='hidden' name='passkey' value='{ADMIN_PASS}'><input name='name' placeholder='Action'><button class='btn'>Add</button></form></div></div></div>"
    
    # মেনু ৩: কন্টেন্ট
    html += f"<div class='admin-card'><h3>🎬 ৩. Content Manager</h3><form action='/admin/add_content' method='post'><input type='hidden' name='passkey' value='{ADMIN_PASS}'><input name='title' placeholder='Title' required><input name='poster' placeholder='Poster URL'><input name='rating' placeholder='Rating'><input name='lang' placeholder='Lang'><input name='actors' placeholder='Actors'><input name='trailer' placeholder='Trailer URL'><input name='quality' placeholder='Quality'><textarea name='desc' placeholder='Description'></textarea><select name='type'><option value='movie'>Movie</option><option value='series'>Series</option></select><select name='cat'>{''.join([f'<option value=\"{c[\"name\"]}\">{c[\"name\"]}</option>' for c in cats])}</select><select name='ott'>{''.join([f'<option value=\"{o[\"_id\"]}\">{o[\"name\"]}</option>' for o in otts])}</select>JSON: <textarea name='json' rows='4'></textarea><button class='btn'>Publish</button></form></div>"
    
    html += "</div></body></html>"
    return html

# --- অ্যাডমিন পোস্ট হ্যান্ডলারস ---
@app.post("/admin/settings")
async def save_settings(passkey: str=Form(...), site_name: str=Form(...), notice: str=Form(...), total_steps: int=Form(...), ad_urls: str=Form(...), popunder: str=Form("")):
    if passkey != ADMIN_PASS: return "Unauthorized"
    await settings_col.update_one({"type": "global"}, {"$set": {"site_name": site_name, "notice": notice, "total_steps": total_steps, "ad_step_urls": ad_urls, "popunder": popunder}}, upsert=True)
    return RedirectResponse(url=f"/admin?passkey={ADMIN_PASS}", status_code=303)

@app.get("/admin/start_bot")
async def start_bot(passkey: str = Query(None)):
    if passkey != ADMIN_PASS: return "Unauthorized"
    if not bot.is_connected:
        await bot.start()
    return RedirectResponse(url=f"/admin?passkey={ADMIN_PASS}", status_code=303)

@app.post("/admin/add_content")
async def add_content(passkey: str=Form(...), title: str=Form(...), poster: str=Form(...), rating: str=Form(...), lang: str=Form(...), actors: str=Form(...), trailer: str=Form(...), quality: str=Form(...), desc: str=Form(...), type: str=Form(...), cat: str=Form(...), ott: str=Form(...), json_data: str=Form(None, alias="json")):
    if passkey != ADMIN_PASS: return "Unauthorized"
    import json as pyjson
    data = pyjson.loads(json_data) if json_data else []
    doc = {"title": title, "poster": poster, "rating": rating, "language": lang, "actors": actors, "trailer": trailer, "quality": quality, "description": desc, "type": type, "category": cat, "ott_id": ott}
    if type == 'movie': doc['qualities'] = data
    else: doc['seasons'] = data
    await content_col.insert_one(doc)
    return RedirectResponse(url=f"/admin?passkey={ADMIN_PASS}", status_code=303)

@app.post("/admin/add_ott")
async def add_ott(passkey: str=Form(...), name: str=Form(...), logo: str=Form(...)):
    if passkey != ADMIN_PASS: return "Unauthorized"
    await ott_col.insert_one({"name": name, "logo": logo})
    return RedirectResponse(url=f"/admin?passkey={ADMIN_PASS}", status_code=303)

@app.post("/admin/add_cat")
async def add_cat(passkey: str=Form(...), name: str=Form(...)):
    if passkey != ADMIN_PASS: return "Unauthorized"
    await category_col.insert_one({"name": name})
    return RedirectResponse(url=f"/admin?passkey={ADMIN_PASS}", status_code=303)

# --- বট ইভেন্ট ও ব্যাকগ্রাউন্ড ---
@bot.on_message(filters.chat(CHANNEL_ID) & (filters.video | filters.document))
async def auto_post(client, message):
    title = message.caption or "Auto Update"
    link = f"https://t.me/c/{str(CHANNEL_ID)[4:]}/{message.id}"
    await content_col.insert_one({"title": title, "poster": "", "type": "movie", "category": "General", "ott_id": "", "qualities": [{"quality": "Original File", "link": link}]})

@app.on_event("startup")
async def startup_event():
    try:
        # বটটিকে ব্যাকগ্রাউন্ডে স্টার্ট করার চেষ্টা
        asyncio.create_task(bot.start())
    except Exception as e:
        print(f"Bot start failed: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
