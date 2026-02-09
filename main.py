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
import pytz

load_dotenv()

# ───────────────── CONFIG ─────────────────
# Use environment variables or fallback to your provided keys
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MONGO_URL = os.environ.get("MONGO_URL", "")
ADMINS = [int(i) for i in os.getenv("ADMINS", "2117119246").split()]

AROLINKS_API = "7a04b0ba40696303483cd4be8541a1a8d831141f"
TVKURL_API = "9986767adc94f9d0a46a66fe436a9ba577c74f1f"

# ───────────────── MONGODB ─────────────────
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
users_collection = db["users"]
tokens_collection = db["tokens"]
config_collection = db["config"]

# ───────────────── BOT START ─────────────────
Bot = Client("Play-Store-Bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ───────────────── HELPERS ─────────────────

async def get_short_link(url: str, api_url_template: str, api_key: str) -> str:
    """Generic function to handle shortening"""
    encoded_url = urllib.parse.quote(url)
    # Both Tvkurl and Arolinks use the same standard API format
    full_api_url = f"{api_url_template}?api={api_key}&url={encoded_url}&format=text"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(full_api_url, timeout=15) as response:
                if response.status == 200:
                    res_text = await response.text()
                    return res_text.strip()
                else:
                    print(f"API Error: Status {response.status}")
                    return url
    except Exception as e:
        print(f"Shortener Request Failed: {e}")
        return url

async def build_double_short_link(bot, token):
    me = await bot.get_me()
    # 1. Create the base Telegram link
    base_url = f"https://t.me/{me.username}?start=GL{token}"
    
    # 2. Shorten with TVKURL first
    print(f"Shortening with TVKURL: {base_url}")
    tvk_link = await get_short_link(base_url, "https://tvkurl.com/api", TVKURL_API)
    
    # 3. Shorten the TVK result with AROLINKS
    print(f"Shortening TVK link with AROLINKS: {tvk_link}")
    final_link = await get_short_link(tvk_link, "https://arolinks.com/api", AROLINKS_API)
    
    return final_link

# ───────────────── HANDLERS ─────────────────

@Bot.on_message(filters.command("start") & filters.private)
async def start_handler(bot, message):
    user_id = message.from_user.id
    
    # Check if user is coming back from a shortlink
    if len(message.command) > 1 and message.command[1].startswith("GL"):
        token = message.command[1][2:]
        tok_data = tokens_collection.find_one({"_id": token})
        
        if tok_data:
            if tok_data['used']:
                return await message.reply("❌ This link has already been used.")
            
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("Verify Final Step ✅", callback_data=f"final:{token}")]])
            return await message.reply("🎉 You have successfully bypassed the links!\nClick below to get your code.", reply_markup=btn)
        else:
            return await message.reply("❌ Invalid or expired session.")

    # Normal Start
    users_collection.update_one({"_id": user_id}, {"$set": {"_id": user_id}}, upsert=True)
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("Generate Code 🔑", callback_data="gen")]])
    await message.reply("Welcome! Click below to start the verification process.", reply_markup=btn)

@Bot.on_callback_query(filters.regex("^gen$"))
async def gen_callback(bot, query):
    user_id = query.from_user.id
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    
    # Store in DB
    tokens_collection.insert_one({
        "_id": token,
        "user_id": user_id,
        "used": False,
        "date": datetime.now(pytz.timezone('Asia/Kolkata'))
    })
    
    await query.message.edit("🔄 Generating your secure links... please wait.")
    
    # Generate the double-layered link
    verify_link = await build_double_short_link(bot, token)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Click to Verify (Step 1/2)", url=verify_link)],
        [InlineKeyboardButton("How to Verify? ❓", url="https://t.me/kpslinkteam/52")]
    ])
    
    await query.message.edit("✅ **Link Generated!**\n\nComplete the Arolinks and Tvkurl steps to get your code.", reply_markup=kb)

@Bot.on_callback_query(filters.regex(r"^final:(.+)$"))
async def final_callback(bot, query):
    token = query.matches[0].group(1)
    # Mark as used and give reward (logic for get_current_code() goes here)
    tokens_collection.update_one({"_id": token}, {"$set": {"used": True}})
    await query.message.edit("✅ **Verified!** Your code is: `FREE-REDEEM-123` (Change this to your logic)")

# ───────────────── SERVER ─────────────────
def run_server():
    class H(BaseHTTPRequestHandler):
        def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"Alive")
    HTTPServer(("0.0.0.0", 8080), H).serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    print("Bot is starting...")
    Bot.run()
