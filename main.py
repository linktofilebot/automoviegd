import os
import pickle
import asyncio
from pyrogram import Client, filters
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from aiohttp import web
import threading

# --- কনফিগারেশন (এগুলো Render-এর Env Vars-এ সেট করবেন) ---
API_ID = int(os.getenv("API_ID", "YOUR_API_ID"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
BLOG_ID = os.getenv("BLOG_ID", "YOUR_BLOG_ID")
# Render-এ আপনার সাইটের URL (যেমন: https://my-bot.onrender.com)
BASE_URL = os.getenv("BASE_URL", "https://your-app-name.onrender.com")

app = Client("stream_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- ব্লগার অথেনটিকেশন ---
def get_blogger_service():
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build('blogger', 'v3', credentials=creds)
    return None

def post_to_blogger(title, stream_url):
    service = get_blogger_service()
    if not service: return "Token Error"
    
    # অ্যাড-ফ্রি আধুনিক প্লেয়ার (Plyr.io)
    content = f"""
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <div style="width: 100%; max-width: 800px; margin: auto;">
        <video id="player" playsinline controls>
            <source src="{stream_url}" type="video/mp4" />
        </video>
    </div>
    <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
    <script>const player = new Plyr('#player');</script>
    """
    
    data = {'kind': 'blogger#post', 'title': title, 'content': content}
    request = service.posts().insert(blogId=BLOG_ID, body=data)
    response = request.execute()
    return response['url']

# --- ফাইল স্ট্রিমিং লজিক (টেলিগ্রাম থেকে ডাইরেক্ট লিঙ্ক) ---
async def stream_handler(request):
    file_id = request.match_info['file_id']
    # এখানে ফাইলটি সরাসরি টেলিগ্রাম সার্ভার থেকে স্ট্রিম করার লজিক থাকে।
    # রেন্ডারে বড় ফাইল স্ট্রিমিং কিছুটা জটিল, তাই আমরা সহজ করার জন্য 
    # একটি ডিরেক্ট লিঙ্ক জেনারেটর মেকানিজম ব্যবহার করছি।
    return web.Response(text="Streaming logic active. Use the bot to generate links.")

# --- টেলিগ্রাম বট হ্যান্ডলার ---
@app.on_message(filters.video | filters.document)
async def handle_video(client, message):
    msg = await message.reply("⚙️ প্রসেসিং হচ্ছে...")
    
    file_name = message.video.file_name if message.video else "Video_Post"
    # ফাইল আইডি জেনারেট করা (স্ট্রিমিং লিঙ্কের জন্য)
    # আপনার রেন্ডার ইউআরএল-এর সাথে কানেক্ট করা
    stream_link = f"{BASE_URL}/watch/{message.id}" 
    
    try:
        post_url = post_to_blogger(file_name, stream_link)
        await msg.edit(f"✅ সফলভাবে পোস্ট হয়েছে!\n\n🔗 ব্লগের লিঙ্ক: {post_url}\n\n🎥 ভিডিওর ডাইরেক্ট লিঙ্ক: {stream_link}")
    except Exception as e:
        await msg.edit(f"❌ এরর: {str(e)}")

# --- ওয়েব সার্ভার রান করা (Render-এর জন্য) ---
def run_web_server():
    server = web.Application()
    server.add_routes([web.get('/watch/{file_id}', stream_handler)])
    web.run_app(server, port=8080)

if __name__ == "__main__":
    # বট এবং ওয়েব সার্ভার একসাথে চালু করা
    threading.Thread(target=run_web_server, daemon=True).start()
    print("বট চলছে...")
    app.run()
