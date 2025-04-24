import os
import threading
import random
import string
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from pyrogram.types import *
from pymongo import MongoClient
from dotenv import load_dotenv
import pytz

load_dotenv()

# MongoDB setup
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
config_collection = db["hourly_links"]
users_collection = db["users"]

ADMINS = [int(i) for i in os.getenv("ADMINS", "").split()]

# Telegram Bot setup
Bot = Client(
    "RedeemBot",
    bot_token=os.environ["BOT_TOKEN"],
    api_id=int(os.environ["API_ID"]),
    api_hash=os.environ["API_HASH"]
)

FORCE_SUB_LINKS = os.getenv("FORCE_SUB_LINKS", "").split()

def generate_random_hash():
    return ''.join(random.choices(string.hexdigits.lower(), k=64))

def get_current_hour_key():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)
    return now.strftime("%-I%p").lower()  # e.g. 6am, 7pm

@Bot.on_message(filters.command("start") & filters.private)
async def start(bot, message):
    user_id = message.from_user.id
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id})

    buttons = [[InlineKeyboardButton("Join Channel", url=url)] for url in FORCE_SUB_LINKS]
    buttons.append([InlineKeyboardButton("Verify", callback_data="verify")])
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply("**JOIN ALL CHANNELS TO USE THIS BOT**", reply_markup=reply_markup)

@Bot.on_callback_query(filters.regex("verify"))
async def verify_channels(bot, query):
    await query.message.delete()
    await query.message.reply(
        "**Welcome! Click below to generate your redeem code:**",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Generate Code", callback_data="gen_code")]])
    )

@Bot.on_callback_query(filters.regex("gen_code"))
async def generate_code(bot, query):
    current_hour = get_current_hour_key()
    config = config_collection.find_one({"_id": current_hour}) or {}
    url = config.get("url", "https://default.com")
    hash_code = generate_random_hash()
    image_url = "https://envs.sh/CCn.jpg"

    caption = (
        "**Your Redeem Code Generated successfully!**
"
        "✅ IF ANY PROBLEM CONTACT HERE @Paidpanelbot

"
        f"`hash:` `{hash_code}`
"
        f"**Code :** `{url}`"
    )
    buttons = InlineKeyboardMarkup([[InlineKeyboardButton("Generate Again", callback_data="gen_code")]])
    await bot.send_photo(
        chat_id=query.message.chat.id,
        photo=image_url,
        caption=caption,
        reply_markup=buttons
    )
    await query.answer()

@Bot.on_message(filters.command("time") & filters.private)
async def set_hour_link(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized to use this command.")
    try:
        parts = message.text.split(None, 2)
        hour_key = parts[1].lower()
        url = parts[2]
        config_collection.update_one({"_id": hour_key}, {"$set": {"url": url}}, upsert=True)
        await message.reply(f"Link set for {hour_key} as {url}")
    except:
        await message.reply("Format:
/time 6am https://link.com")

# Broadcast
@Bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("Not authorized.")
    if len(message.command) < 2:
        return await message.reply("Usage: /broadcast <message>")
    text = message.text.split(None, 1)[1]
    count = 0
    for user in users_collection.find():
        try:
            await bot.send_message(chat_id=user['_id'], text=text)
            count += 1
        except:
            continue
    await message.reply(f"Message sent to {count} users.")

# Health check
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_server():
    server = HTTPServer(("0.0.0.0", 8080), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_server).start()
Bot.run()
    
