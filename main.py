import os
import logging
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
from pymongo import MongoClient

# --- Flask Server (Render এর পোর্ট সমস্যা সমাধানের জন্য) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_flask():
    # Render পোর্ট এনভায়রনমেন্ট ভ্যারিয়েবল থেকে পোর্ট নেয়
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- Logging setup ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Environment Variables (Render-এ সেট করবেন) ---
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# MongoDB Connection
client = MongoClient(MONGO_URI)
db = client['telegram_post_bot']
users_col = db['users_data']

# Conversation States
POSTER, VIDEO_LINK = range(2)
CAP_NAME, CAP_LINK = range(2, 4)
DATE_INPUT = 4
CHANNEL_INPUT = 5

# --- Helper Functions (Database operations) ---
def get_user_data(user_id):
    data = users_col.find_one({"user_id": user_id})
    if not data:
        return {"user_id": user_id, "buttons": [], "date": "সেট করা নেই", "channels": []}
    return data

def update_user_data(user_id, update_query):
    users_col.update_one({"user_id": user_id}, update_query, upsert=True)

# --- Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🤖 **টেলিগ্রাম পোস্ট মেকার বট**\n\n"
        "নিচের কমান্ডগুলো ব্যবহার করুন:\n"
        "🔹 /setdate - আজকের তারিখ সেট করতে\n"
        "🔹 /setcap - ফুটার বাটন (নাম ও লিঙ্ক) যোগ করতে\n"
        "🔹 /setchannel - অটো পোস্ট করার জন্য চ্যানেল আইডি এড করতে\n"
        "🔹 /post - আপনার পোস্ট সাজানো শুরু করতে\n\n"
        "🔸 /resetcap - সব বাটন মুছতে\n"
        "🔸 /resetchannel - সব চ্যানেল মুছতে\n"
        "🔸 /cancel - চলমান প্রসেস বাতিল করতে"
    )
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

# --- /setdate (তারিখ সেট করা) ---
async def start_setdate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("আজকের তারিখটি লিখুন (যেমন: ১০ জানুয়ারি ২০২৬):")
    return DATE_INPUT

async def save_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    date_text = update.message.text
    update_user_data(user_id, {"$set": {"date": date_text}})
    await update.message.reply_text(f"✅ তারিখ সেট হয়েছে: {date_text}")
    return ConversationHandler.END

# --- /setcap (বাটন এড করা) ---
async def start_setcap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("বাটনের নাম দিন (যেমন: Join Channel):")
    return CAP_NAME

async def get_cap_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['temp_btn_name'] = update.message.text
    await update.message.reply_text("এবার চ্যানেল বা গ্রুপের লিঙ্ক দিন:")
    return CAP_LINK

async def save_cap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = context.user_data['temp_btn_name']
    url = update.message.text
    if not url.startswith("http"):
        await update.message.reply_text("❌ ভুল লিঙ্ক! দয়া করে সঠিক লিঙ্ক (http/https সহ) দিন।")
        return CAP_LINK
    update_user_data(user_id, {"$push": {"buttons": {"text": name, "url": url}}})
    await update.message.reply_text(f"✅ বাটন '{name}' সেভ হয়েছে।")
    return ConversationHandler.END

# --- /setchannel (অটো ফরওয়ার্ড চ্যানেল আইডি) ---
async def start_setchannel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "আপনার চ্যানেলের আইডিটি দিন (যেমন: -100123456789)\n\n"
        "⚠️ মনে রাখবেন: বটকে অবশ্যই ওই চ্যানেলে এডমিন বানাতে হবে।"
    )
    return CHANNEL_INPUT

async def save_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ch_id = update.message.text.strip()
    update_user_data(user_id, {"$addToSet": {"channels": ch_id}})
    await update.message.reply_text(f"✅ চ্যানেল আইডি {ch_id} সেভ হয়েছে।")
    return ConversationHandler.END

# --- /post (মেইন প্রসেস ও অটো সেন্ড) ---
async def start_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("আপনার পোস্টার (ছবি) টি পাঠান:")
    return POSTER

async def get_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['poster_id'] = update.message.photo[-1].file_id
    await update.message.reply_text("ধন্যবাদ! এবার ভিডিওর লিঙ্কটি দিন:")
    return VIDEO_LINK

async def finalize_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    v_link = update.message.text
    p_id = context.user_data.get('poster_id')
    
    # DB থেকে ডাটা আনা
    user_data = get_user_data(user_id)
    saved_date = user_data.get('date', 'সেট করা নেই')
    buttons = user_data.get('buttons', [])
    target_channels = user_data.get('channels', [])
    
    # পোস্ট সাজানো
    caption = (
        f"📅 তারিখ: {saved_date}\n\n"
        "🎬 **নতুন ভিডিও আপডেট** 🎬\n\n"
        f"🔗 ভিডিও লিঙ্ক: {v_link}\n\n"
        "সবাই লিংকে ক্লিক করে ভিডিওটি দেখে নিন!"
    )
    
    keyboard = [[InlineKeyboardButton(b['text'], url=b['url'])] for b in buttons]
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    # ১. ইউজারকে (আপনাকে) রিপ্লাই দেওয়া
    await update.message.reply_photo(photo=p_id, caption=caption, reply_markup=reply_markup, parse_mode='Markdown')

    # ২. সেভ করা সকল চ্যানেলে অটো সেন্ড
    if target_channels:
        sent_count = 0
        for ch_id in target_channels:
            try:
                await context.bot.send_photo(
                    chat_id=ch_id,
                    photo=p_id,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                sent_count += 1
            except Exception as e:
                await update.message.reply_text(f"⚠️ চ্যানেল {ch_id} এ পোস্ট যায়নি। কারণ: {e}")
        await update.message.reply_text(f"✅ মোট {sent_count}টি চ্যানেলে অটো পোস্ট করা হয়েছে।")
    else:
        await update.message.reply_text("ℹ️ আপনার কোনো চ্যানেল এড করা নেই, তাই কোথাও অটো পোস্ট হয়নি।")

    return ConversationHandler.END

# --- Reset Functions ---
async def reset_cap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_user_data(update.effective_user.id, {"$set": {"buttons": []}})
    await update.message.reply_text("✅ সব বাটন মুছে ফেলা হয়েছে।")

async def reset_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_user_data(update.effective_user.id, {"$set": {"channels": []}})
    await update.message.reply_text("✅ সব চ্যানেল রিমুভ করা হয়েছে।")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("প্রসেস বাতিল করা হয়েছে।")
    return ConversationHandler.END

# --- Main Setup ---
def main():
    if not TOKEN or not MONGO_URI:
        print("BOT_TOKEN or MONGO_URI is missing!")
        return

    # Flask running in thread to bypass Render's port check
    threading.Thread(target=run_flask, daemon=True).start()

    application = Application.builder().token(TOKEN).build()

    # Conversation Handlers
    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("post", start_post)],
        states={
            POSTER: [MessageHandler(filters.PHOTO, get_poster)],
            VIDEO_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_post)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("setcap", start_setcap)],
        states={
            CAP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_cap_name)],
            CAP_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_cap)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("setdate", start_setdate)],
        states={DATE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_date)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    application.add_handler(ConversationHandler(
        entry_points=[CommandHandler("setchannel", start_setchannel)],
        states={CHANNEL_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_channel)]},
        fallbacks=[CommandHandler("cancel", cancel)]
    ))

    # General Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("resetcap", reset_cap))
    application.add_handler(CommandHandler("resetchannel", reset_channel))

    print("Bot is starting...")
    application.run_polling()

if __name__ == "__main__":
    main()
