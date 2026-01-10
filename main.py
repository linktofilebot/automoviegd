import os
import logging
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

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Environment Variables (রেন্ডারে এগুলো সেট করবেন)
TOKEN = os.getenv("BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")

# MongoDB Connection
client = MongoClient(MONGO_URI)
db = client['telegram_post_bot']
users_col = db['users_data']

# States for Conversations
POSTER, VIDEO_LINK = range(2)
CAP_NAME, CAP_LINK = range(2, 4)
DATE_INPUT = 4

# --- Helper Functions ---
def get_user_data(user_id):
    data = users_col.find_one({"user_id": user_id})
    if not data:
        return {"user_id": user_id, "buttons": [], "date": "সেট করা নেই"}
    return data

def update_user_data(user_id, update_query):
    users_col.update_one({"user_id": user_id}, update_query, upsert=True)

# --- Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "স্বাগতম! নিচের কমান্ডগুলো ব্যবহার করুন:\n"
        "/post - নতুন পোস্ট তৈরি করতে\n"
        "/setdate - তারিখ সেট করতে\n"
        "/setcap - ফুটার বাটন যোগ করতে\n"
        "/resetcap - সব বাটন মুছে ফেলতে"
    )

# --- /setdate Command ---
async def start_setdate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("আজকের তারিখটি লিখুন (যেমন: ১০ জানুয়ারি ২০২৬):")
    return DATE_INPUT

async def save_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    date_text = update.message.text
    update_user_data(user_id, {"$set": {"date": date_text}})
    await update.message.reply_text(f"✅ তারিখ সেট হয়েছে: {date_text}")
    return ConversationHandler.END

# --- /setcap Command ---
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
        await update.message.reply_text("❌ ভুল লিঙ্ক! দয়া করে সঠিক লিঙ্ক দিন।")
        return CAP_LINK

    update_user_data(user_id, {"$push": {"buttons": {"text": name, "url": url}}})
    await update.message.reply_text(f"✅ বাটন '{name}' সেভ হয়েছে। আপনি চাইলে আরও বাটন যোগ করতে পারেন।")
    return ConversationHandler.END

# --- /post Command ---
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
    p_id = context.user_data['poster_id']
    
    # DB থেকে ডাটা আনা
    user_data = get_user_data(user_id)
    saved_date = user_data.get('date', 'সেট করা নেই')
    buttons = user_data.get('buttons', [])
    
    # পোস্টের ক্যাপশন সাজানো
    caption = (
        f"📅 তারিখ: {saved_date}\n\n"
        "🎬 **নতুন ভিডিও আপডেট** 🎬\n\n"
        f"🔗 ভিডিও লিঙ্ক: {v_link}\n\n"
        "সবাই লিংকে ক্লিক করে ভিডিওটি দেখে নিন!"
    )
    
    # বাটন সাজানো
    keyboard = [[InlineKeyboardButton(b['text'], url=b['url'])] for b in buttons]
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    await update.message.reply_photo(
        photo=p_id,
        caption=caption,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return ConversationHandler.END

# --- Cancel/Reset ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("অপারেশন বাতিল করা হয়েছে।")
    return ConversationHandler.END

async def reset_cap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_user_data(update.effective_user.id, {"$set": {"buttons": []}})
    await update.message.reply_text("✅ আপনার সব বাটন মুছে ফেলা হয়েছে।")

# --- Main Function ---
def main():
    if not TOKEN or not MONGO_URI:
        print("Error: BOT_TOKEN বা MONGO_URI সেট করা হয়নি!")
        return

    application = Application.builder().token(TOKEN).build()

    # /post Handler
    post_conv = ConversationHandler(
        entry_points=[CommandHandler("post", start_post)],
        states={
            POSTER: [MessageHandler(filters.PHOTO, get_poster)],
            VIDEO_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_post)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # /setcap Handler
    cap_conv = ConversationHandler(
        entry_points=[CommandHandler("setcap", start_setcap)],
        states={
            CAP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_cap_name)],
            CAP_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_cap)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # /setdate Handler
    date_conv = ConversationHandler(
        entry_points=[CommandHandler("setdate", start_setdate)],
        states={
            DATE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("resetcap", reset_cap))
    application.add_handler(post_conv)
    application.add_handler(cap_conv)
    application.add_handler(date_conv)

    print("বট চলছে...")
    application.run_polling()

if __name__ == "__main__":
    main()
