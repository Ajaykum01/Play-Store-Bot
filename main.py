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

# ───────────────── MongoDB ─────────────────
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
config_collection = db["config"]
users_collection = db["users"]
tokens_collection = db["tokens"]

ADMINS = [int(i) for i in os.getenv("ADMINS", "2117119246").split()]

# ───────────────── Bot ─────────────────
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

# ───────────────── API CONFIG ─────────────────
AROLINKS_API = "7a04b0ba40696303483cd4be8541a1a8d831141f"
TVKURL_API = "9986767adc94f9d0a46a66fe436a9ba577c74f1f"

# ───────────────── Codes Logic ─────────────────
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

# ───────────────── Helpers ─────────────────
def gen_token(n: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(random.choices(alphabet, k=n))

async def shorten_with_tvkurl(long_url: str) -> str:
    """Shortens the link using TVKURL API first"""
    encoded_url = urllib.parse.quote_plus(long_url)
    api_url = f"https://tvkurl.com/api?api={TVKURL_API}&url={encoded_url}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=20) as resp:
                text = (await resp.text()).strip()
                return text if text.startswith("http") else long_url
    except Exception:
        return long_url

async def shorten_with_arolinks(long_url: str) -> str:
    """Shortens the already shortened TVK link with Arolinks"""
    encoded_url = urllib.parse.quote_plus(long_url)
    api_url = f"https://arolinks.com/api?api={AROLINKS_API}&url={encoded_url}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=20) as resp:
                text = (await resp.text()).strip()
                return text if text.startswith("http") else long_url
    except Exception:
        return long_url

async def build_verify_link(bot: Client, token: str) -> str:
    me = await bot.get_me()
    deep_link = f"https://t.me/{me.username}?start=GL{token}"
    
    # Nested Shortening: Tvkurl -> Arolinks
    tvk_short = await shorten_with_tvkurl(deep_link)
    final_short = await shorten_with_arolinks(tvk_short)
    
    return final_short

def ensure_user(user_id: int):
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id})

# ───────────────── Handlers ─────────────────
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
                return await message.reply("⚠️ This link belongs to another account.")  

            if tok.get("used"):  
                return await message.reply("ℹ️ Already verified.")  

            btn = InlineKeyboardMarkup([[InlineKeyboardButton("Verify now by clicking me✅", callback_data=f"final_verify:{token}")]])  
            return await message.reply("✅ Redirection completed!\n\nTap below to claim your code.", reply_markup=btn)  

    buttons = [[InlineKeyboardButton("Subscribe Channel 😎", url=url)] for url in FORCE_SUB_LINKS]  
    buttons.append([InlineKeyboardButton("Verify ✅", callback_data="verify")])  
    await message.reply("**JOIN GIVEN CHANNEL TO GET REDEEM CODE**", reply_markup=InlineKeyboardMarkup(buttons))

@Bot.on_callback_query(filters.regex("^verify$"))
async def verify_channels(bot, query):
    await query.message.delete()
    await query.message.reply(
        "🙏 Welcome to NST Free Google Play Redeem Code Bot\nClick Generate Code to start.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Generate Code", callback_data="gen_code")]])
    )

@Bot.on_callback_query(filters.regex("^gen_code$"))
async def generate_code(bot, query):
    user_id = query.from_user.id
    ensure_user(user_id)
    token = gen_token()  
    tokens_collection.insert_one({"_id": token, "user_id": user_id, "used": False, "created_at": datetime.utcnow()})  

    # This calls the nested shortening function
    verify_url = await build_verify_link(bot, token)  

    caption = "🔐 **Verification Required**\n\nStep 1: Complete Arolinks\nStep 2: Complete Tvkurl\nStep 3: Get your Code!"
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton("Verify 🙂", url=verify_url)], [InlineKeyboardButton("How to verify ❓", url=HOW_TO_VERIFY_URL)]])  
    
    try: await query.message.delete()
    except: pass  

    await bot.send_message(user_id, caption, reply_markup=buttons)  
    await query.answer()

@Bot.on_callback_query(filters.regex(r"^final_verify:(.+)$"))
async def final_verify(bot, query):
    user_id = query.from_user.id
    token = query.data.split(":", 1)[1]
    tok = tokens_collection.find_one({"_id": token})  
    
    if not tok or tok.get("used"): return await query.answer("Invalid Token.", show_alert=True)  

    tokens_collection.update_one({"_id": token}, {"$set": {"used": True, "used_at": datetime.utcnow()}})  
    code = get_current_code()  
    caption = f"✅ Success!\n\n🎁 Redeem Code:- `{code}`" if code else "❌ No codes left."
    
    await bot.send_message(user_id, caption, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Generate Again", callback_data="gen_code")]]))  
    await query.answer("Verified ✅")

# ───────────────── Admin & Health ─────────────────
@Bot.on_message(filters.command("time") & filters.private)
async def set_codes(bot, message):
    if message.from_user.id not in ADMINS: return
    parts = message.text.split()[1:]
    if not parts: return await message.reply("Usage: /time CODE1 CODE2")
    save_codes(parts)
    await message.reply(f"✅ {len(parts)} codes set.")

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_server():
    HTTPServer(("0.0.0.0", 8080), HealthCheckHandler).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    Bot.run()
