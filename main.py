import os
import threading
import random
import string
import asyncio
import aiohttp
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# ───────────────── MongoDB ───────────────── #
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
config_collection = db["config"]
users_collection = db["users"]
tokens_collection = db["tokens"]

ADMINS = [int(i) for i in os.getenv("ADMINS", "2117119246").split()]

# ───────────────── Bot ───────────────── #
Bot = Client(
    "Play-Store-Bot",
    bot_token=os.environ["BOT_TOKEN"],
    api_id=int(os.environ["API_ID"]),
    api_hash=os.environ["API_HASH"]
)

HOW_TO_VERIFY_URL = "https://t.me/kpslinkteam/52"
FORCE_SUB_LINKS = [
    "https://telegram.me/+Iyc7cjYrBpxlOWM1",
    "https://telegram.me/+poyQjeODmb0wMjhl",
    "https://telegram.me/ffunusedaccountbot",
]

# ───────────────── APIs ───────────────── #
AROLINKS_API = "7a04b0ba40696303483cd4be8541a1a8d831141f"

TVK_API = "9986767adc94f9d0a46a66fe436a9ba577c74f1f"
TVK_API_ENDPOINT = "https://tvkurl.com/api"

# ───────────────── Codes ───────────────── #
def load_codes():
    config = config_collection.find_one({"_id": "codes"}) or {}
    return config.get("codes", [])

def save_codes(codes: list):
    config_collection.update_one({"_id": "codes"}, {"$set": {"codes": codes}}, upsert=True)

def get_current_code():
    codes = load_codes()
    if not codes:
        return None
    code = codes.pop(0)
    save_codes(codes)
    return code

# ───────────────── Helpers ───────────────── #
def gen_token(n: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(random.choices(alphabet, k=n))

async def shorten_with_tvk(long_url: str) -> str:
    params = {
        "api": TVK_API,
        "url": long_url,
        "format": "text"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(TVK_API_ENDPOINT, params=params, timeout=20) as resp:
                text = (await resp.text()).strip()
                if text.startswith("http"):
                    return text
                return ""
    except Exception:
        return ""

async def shorten_with_arolinks(long_url: str) -> str:
    encoded_url = urllib.parse.quote_plus(long_url)
    api_url = f"https://arolinks.com/api?api={AROLINKS_API}&url={encoded_url}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=20) as resp:
                text = (await resp.text()).strip()
                if text.startswith("http"):
                    return text
                return ""
    except Exception:
        return ""

async def build_verify_link(bot: Client, token: str) -> str:
    me = await bot.get_me()
    deep_link = f"https://t.me/{me.username}?start=GL{token}"

    tvk_short = await shorten_with_tvk(deep_link)
    if not tvk_short:
        tvk_short = deep_link

    aro_short = await shorten_with_arolinks(tvk_short)
    return aro_short or tvk_short

def ensure_user(user_id: int):
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id})

# ───────────────── Handlers ───────────────── #
@Bot.on_message(filters.command("start") & filters.private)
async def start(bot, message):
    user_id = message.from_user.id
    ensure_user(user_id)

    if len(message.command) > 1:
        payload = message.command[1]
        if payload.startswith("GL"):
            token = payload[2:]
            tok = tokens_collection.find_one({"_id": token})
            if not tok:
                return await message.reply("⚠️ Token not found or expired.")

            if tok.get("user_id") != user_id:
                return await message.reply("⚠️ This link belongs to another user.")

            if tok.get("used"):
                return await message.reply("ℹ️ Token already verified.")

            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Verify now by clicking me✅", callback_data=f"final_verify:{token}")]
            ])
            return await message.reply(
                "✅ Short link completed!\n\nTap the button below to complete verification.",
                reply_markup=btn
            )

    buttons = [[InlineKeyboardButton("Subscribe Channel 😎", url=url)] for url in FORCE_SUB_LINKS]
    buttons.append([InlineKeyboardButton("Verify ✅", callback_data="verify")])
    await message.reply("**JOIN GIVEN CHANNEL TO GET REDEEM CODE**", reply_markup=InlineKeyboardMarkup(buttons))

@Bot.on_callback_query(filters.regex("^verify$"))
async def verify_channels(bot, query):
    await query.message.delete()
    await query.message.reply(
        "🙏 Welcome to NST Free Google Play Redeem Code Bot RS30-200 🪙",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Generate Code", callback_data="gen_code")]])
    )

@Bot.on_callback_query(filters.regex("^gen_code$"))
async def generate_code(bot, query):
    user_id = query.from_user.id
    ensure_user(user_id)

    token = gen_token()
    tokens_collection.insert_one({
        "_id": token,
        "user_id": user_id,
        "used": False,
        "created_at": datetime.utcnow()
    })

    verify_url = await build_verify_link(bot, token)

    caption = (
        "🔐 **Verification Required**\n\n"
        "1) Tap **Verify 🙂**\n"
        "2) Complete steps\n"
        "3) Return here automatically"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Verify 🙂", url=verify_url)],
        [InlineKeyboardButton("How to verify ❓", url=HOW_TO_VERIFY_URL)],
    ])

    try:
        await query.message.delete()
    except Exception:
        pass

    await bot.send_message(user_id, caption, reply_markup=buttons, disable_web_page_preview=True)
    await query.answer()

@Bot.on_callback_query(filters.regex(r"^final_verify:(.+)$"))
async def final_verify(bot, query):
    user_id = query.from_user.id
    token = query.data.split(":", 1)[1]

    tok = tokens_collection.find_one({"_id": token})
    if not tok or tok.get("user_id") != user_id or tok.get("used"):
        return await query.answer("Verification failed.", show_alert=True)

    tokens_collection.update_one(
        {"_id": token},
        {"$set": {"used": True, "used_at": datetime.utcnow()}}
    )

    code = get_current_code()
    caption = f"🎁 Redeem Code:- `{code}`" if code else "❌ No codes available."

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Generate Again", callback_data="gen_code")]
    ])

    try:
        await query.message.delete()
    except Exception:
        pass

    await bot.send_message(user_id, caption, reply_markup=buttons, disable_web_page_preview=True)
    await query.answer("Verified ✅")

# ───────────────── Health Check ───────────────── #
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_server():
    server = HTTPServer(("0.0.0.0", 8080), HealthCheckHandler)
    server.serve_forever()

# ───────────────── Main ───────────────── #
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    Bot.run()
