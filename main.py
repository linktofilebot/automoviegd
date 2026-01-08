import os
import pickle
import threading
from flask import Flask, request, Response
from pyrogram import Client, filters
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# --- কনফিগারেশন (Render Environment Variables থেকে আসবে) ---
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BLOG_ID = os.getenv("BLOG_ID", "")
BASE_URL = os.getenv("BASE_URL", "") # উদা: https://your-app.onrender.com
PORT = int(os.getenv("PORT", 10000))

# --- ১. ফ্লাস্ক ওয়েব সার্ভার সেটআপ (Render-এর জন্য) ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "🔥 Bot is Live and Server is Running!"

# ভিডিও স্ট্রিমিং রুট (এটি সরাসরি ভিডিও লিঙ্ক হিসেবে কাজ করবে)
@web_app.route('/stream/<int:message_id>')
def stream_video(message_id):
    # এটি একটি ডিরেক্ট লিঙ্ক জেনারেটর লজিক (কনসেপ্ট)
    # রেন্ডারে সরাসরি ফাইল স্ট্রিমিং করতে হলে ফাইলটি ডাউনলোড করতে হয়
    # যা ফ্রি টায়ারে সম্ভব না হতে পারে। তবে এটি ব্লগারে প্লেয়ার লোড করতে সাহায্য করবে।
    return Response(f"Streaming link for message {message_id} is active.", mimetype='text/plain')

def run_flask():
    web_app.run(host='0.0.0.0', port=PORT)

# --- ২. ব্লগার এপিআই লজিক ---
def get_blogger_service():
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build('blogger', 'v3', credentials=creds)
    return None

def post_to_blogger(title, stream_url):
    service = get_blogger_service()
    if not service:
        return None

    # অ্যাড-ফ্রি আধুনিক প্লেয়ার (Plyr.io)
    content = f"""
    <link rel="stylesheet" href="https://cdn.plyr.io/3.7.8/plyr.css" />
    <div style="width: 100%; max-width: 800px; margin: auto;">
        <video id="player" playsinline controls style="width:100%; border-radius: 8px;">
            <source src="{stream_url}" type="video/mp4" />
        </video>
    </div>
    <script src="https://cdn.plyr.io/3.7.8/plyr.js"></script>
    <script>const player = new Plyr('#player');</script>
    <br>
    <p style="text-align:center;">ভিডিওটি আমাদের সাইটে অ্যাড-ফ্রি দেখুন।</p>
    """

    data = {
        'kind': 'blogger#post',
        'title': title,
        'content': content
    }
    
    try:
        posts = service.posts()
        request = posts.insert(blogId=BLOG_ID, body=data)
        response = request.execute()
        return response['url']
    except Exception as e:
        print(f"Blogger Post Error: {e}")
        return None

# --- ৩. টেলিগ্রাম বট লজিক (Pyrogram) ---
bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@bot.on_message(filters.video | filters.document)
async def video_handler(client, message):
    if message.video or (message.document and "video" in message.document.mime_type):
        status_msg = await message.reply("⚡ ভিডিওটি প্রসেস হচ্ছে... ব্লগারে পোস্ট করা হচ্ছে।")
        
        # ফাইলের নাম ঠিক করা
        file_name = message.video.file_name if message.video else message.document.file_name
        if not file_name:
            file_name = "New_Video_Upload"

        # ডাইরেক্ট লিঙ্ক তৈরি (এটি আপনার সার্ভারের লিঙ্ক)
        # রেন্ডারে সরাসরি বড় ভিডিও ফাইল স্ট্রিম করা কঠিন, তাই আমরা একটি পাবলিক ফাস্ট-স্ট্রীম লিঙ্ক তৈরি করার মেকানিজম ব্যবহার করি
        # তবে আপাতত আপনার নিজের সার্ভার ইউআরএল ব্যবহার করছি
        direct_stream_url = f"{BASE_URL}/stream/{message.id}"

        # ব্লগারে পোস্ট করা
        blog_url = post_to_blogger(file_name, direct_stream_url)

        if blog_url:
            await status_msg.edit(f"✅ সফলভাবে পোস্ট হয়েছে!\n\n🔗 **ব্লগ লিঙ্ক:** {blog_url}\n\n🎬 **ভিডিও লিঙ্ক:** {direct_stream_url}")
        else:
            await status_msg.edit("❌ ব্লগার পোস্ট করতে সমস্যা হয়েছে। token.pickle ফাইলটি চেক করুন।")
    else:
        await message.reply("দয়া করে একটি ভিডিও ফাইল পাঠান।")

# --- ৪. মেইন ফাংশন ---
if __name__ == "__main__":
    # Flask সার্ভারকে আলাদা থ্রেডে চালানো
    threading.Thread(target=run_flask, daemon=True).start()
    
    print("Bot is starting...")
    bot.run()
