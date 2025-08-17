import os
import random
import requests
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient

# ===================== CONFIG =====================
API_ID = int(os.getenv("API_ID", "12345"))  # your API_ID from my.telegram.org
API_HASH = os.getenv("API_HASH", "your_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_bot_token")
MONGO_URL = os.getenv("MONGO_URL", "your_mongo_url")

# Admins who can add codes
ADMINS = [123456789]  # Replace with your Telegram user ID

# Shortener API
SHORT_API = "4be71cae8f3aeabe56467793a0ee8f20e0906f3a"
VERIFY_DEST = "https://t.me/kpslinkteam/59"  # link to verify
SHORT_API_URL = f"https://gyanilinks.com/api?api={SHORT_API}&url={VERIFY_DEST}&format=text"

# MongoDB setup
mongo = MongoClient(MONGO_URL)
db = mongo["redeem_bot"]

# Start bot
Bot = Client(
    "redeem_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# ===================== HELPERS =====================
def shorten_verify_link():
    """Return a shortened link using GyaniLinks API"""
    try:
        res = requests.get(SHORT_API_URL, timeout=10)
        if res.status_code == 200:
            return res.text.strip()
    except Exception as e:
        print("Shortener error:", e)
    return VERIFY_DEST  # fallback


def get_fresh_code():
    """Fetch one unused code from DB"""
    code_entry = db["redeem_codes"].find_one_and_update(
        {"used": False},
        {"$set": {"used": True}}
    )
    if code_entry:
        return code_entry["code"]
    return None


# ===================== HANDLERS =====================
@Bot.on_message(filters.command("start"))
async def start(bot, message):
    short_link = shorten_verify_link()
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Verify", url=short_link)],
        [InlineKeyboardButton("ℹ️ How to Verify", url="https://t.me/kpslinkteam/52")],
        [InlineKeyboardButton("🔄 After Verify, Click Here", callback_data="check_verify")]
    ])
    await message.reply(
        "👋 Welcome! To generate a redeem code:\n\n"
        "1️⃣ Click **Verify** and open the link.\n"
        "2️⃣ After visiting, click **After Verify**.\n"
        "3️⃣ You will get your redeem code.\n\n",
        reply_markup=buttons
    )


@Bot.on_callback_query(filters.regex("check_verify"))
async def check_verify(bot, query):
    code = get_fresh_code()
    if not code:
        await query.message.edit(
            "⚠️ Sorry, no redeem codes left. Please try again later."
        )
        return

    caption = (
        "**🎁 Your Redeem Code Generated Successfully ✅**\n\n"
        f"🔗 **Code:** `{code}`\n\n"
        "📌 How to redeem: https://t.me/kpslinkteam/52\n\n"
        "⏳ To get another code, you must verify again."
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Generate Again", callback_data="regen")],
        [InlineKeyboardButton("ℹ️ How to Redeem", url="https://t.me/kpslinkteam/52")]
    ])

    await query.message.edit(caption, reply_markup=buttons)


@Bot.on_callback_query(filters.regex("regen"))
async def regen(bot, query):
    short_link = shorten_verify_link()
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Verify", url=short_link)],
        [InlineKeyboardButton("ℹ️ How to Verify", url="https://t.me/kpslinkteam/52")],
        [InlineKeyboardButton("🔄 After Verify, Click Here", callback_data="check_verify")]
    ])
    await query.message.edit(
        "🔄 Please verify again to generate a new code.",
        reply_markup=buttons
    )


# ===================== ADMIN COMMAND =====================
@Bot.on_message(filters.command("codes") & filters.user(ADMINS))
async def add_codes(bot, message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ Usage: `/codes CODE1 CODE2 CODE3`", quote=True)
        return

    codes = parts[1:]
    for c in codes:
        db["redeem_codes"].insert_one({"code": c, "used": False})

    await message.reply(f"✅ Added {len(codes)} new codes.")


# ===================== RUN BOT =====================
if __name__ == "__main__":
    print("🤖 Bot is starting...")
    Bot.run()
