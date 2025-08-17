import os
import threading
import random
import string
import asyncio
import aiohttp
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from pyrogram.types import *
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
import pytz

load_dotenv()

# ===================== DB SETUP =====================
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
config_collection = db["config"]
users_collection = db["users"]
codes_collection = db["codes"]

ADMINS = [int(i) for i in os.getenv("ADMINS", "2117119246").split()]

# ===================== BOT SETUP =====================
Bot = Client(
    "Play-Store-Bot",
    bot_token=os.environ["BOT_TOKEN"],
    api_id=int(os.environ["API_ID"]),
    api_hash=os.environ["API_HASH"]
)

FORCE_SUB_LINKS = [
    "https://yt.openinapp.co/fatz4",
    "https://yt.openinapp.co/u4hem",
    "https://t.me/+JJdz2hyOVRYyNzE1",
    "https://t.me/+hXaGwny7nVo3NDM9",
]

# ===================== VERIFY SHORT LINK =====================
SHORT_API = "4be71cae8f3aeabe56467793a0ee8f20e0906f3a"
VERIFY_DEST = "https://t.me/kpslinkteam/59"
SHORT_API_URL = f"https://gyanilinks.com/api?api={SHORT_API}&url={VERIFY_DEST}&format=text"

def shorten_verify_link():
    try:
        res = requests.get(SHORT_API_URL, timeout=10)
        if res.status_code == 200:
            return res.text.strip()
    except Exception as e:
        print("Shortener error:", e)
    return VERIFY_DEST

# ===================== HELPERS =====================
def get_fresh_code():
    """Fetch one unused code from DB"""
    code_entry = codes_collection.find_one_and_update(
        {"used": False},
        {"$set": {"used": True}}
    )
    if code_entry:
        return code_entry["code"]
    return None

# ===================== START =====================
@Bot.on_message(filters.command("start") & filters.private)
async def start(bot, message):
    user_id = message.from_user.id
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id})

    buttons = [[InlineKeyboardButton("Subscribe Channel ❤️", url=url)] for url in FORCE_SUB_LINKS]
    short_link = shorten_verify_link()
    buttons.append([InlineKeyboardButton("✅ Verify", url=short_link)])
    buttons.append([InlineKeyboardButton("ℹ️ How to Verify", url="https://t.me/kpslinkteam/52")])
    buttons.append([InlineKeyboardButton("🔄 After Verify", callback_data="check_verify")])

    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply("**JOIN GIVEN CHANNELS & VERIFY TO GET REDEEM CODE**", reply_markup=reply_markup)

# ===================== VERIFY & GIVE CODE =====================
@Bot.on_callback_query(filters.regex("check_verify"))
async def check_verify(bot, query):
    code = get_fresh_code()
    if not code:
        await query.message.edit("⚠️ Sorry, no redeem codes left. Contact admin.")
        return

    caption = (
        "🙏 Welcome to NST Free Google Play Redeem Code Bot 🪙\n\n"
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
    buttons = [
        [InlineKeyboardButton("✅ Verify", url=short_link)],
        [InlineKeyboardButton("ℹ️ How to Verify", url="https://t.me/kpslinkteam/52")],
        [InlineKeyboardButton("🔄 After Verify", callback_data="check_verify")]
    ]
    await query.message.edit("🔄 Please verify again to generate a new code.", reply_markup=InlineKeyboardMarkup(buttons))

# ===================== ADMIN COMMANDS =====================
@Bot.on_message(filters.command("codes") & filters.private)
async def add_codes(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("❌ You are not authorized.")
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply("❌ Usage: `/codes CODE1 CODE2 CODE3`")
    codes = parts[1:]
    for c in codes:
        codes_collection.insert_one({"code": c, "used": False})
    await message.reply(f"✅ Added {len(codes)} codes.")

# ===================== BROADCAST =====================
@Bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized to use this command.")
    if len(message.command) < 2:
        return await message.reply("Usage: /broadcast <your message>")
    broadcast_text = message.text.split(None, 1)[1]
    count = 0
    for user in users_collection.find():
        try:
            await bot.send_message(chat_id=user['_id'], text=broadcast_text)
            count += 1
        except:
            continue
    await message.reply(f"Broadcast sent to {count} users.")

# ===================== HEALTH CHECK =====================
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_server():
    server = HTTPServer(("0.0.0.0", 8080), HealthCheckHandler)
    server.serve_forever()

async def auto_ping():
    await Bot.start()
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                await session.get("https://jittery-merna-agnalagnal4-8c1a65b0.koyeb.app/")
        except:
            pass
        await asyncio.sleep(300)

# ===================== RUN =====================
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    loop = asyncio.get_event_loop()
    loop.create_task(auto_ping())
    Bot.run()    """Return a shortened link using GyaniLinks API"""
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
