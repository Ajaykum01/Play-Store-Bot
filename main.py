import os
import threading
import random
import string
import json
import asyncio
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters, idle
from pyrogram.types import *
from pymongo import MongoClient
from dotenv import load_dotenv
import pytz

load_dotenv()

# MongoDB setup
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
config_collection = db["config"]
users_collection = db["users"]

ADMINS = [int(i) for i in os.getenv("ADMINS", "2117119246").split()]
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))  # Set your channel or group ID

# Telegram Bot setup
Bot = Client(
    "Play-Store-Bot",
    bot_token=os.environ["BOT_TOKEN"],
    api_id=int(os.environ["API_ID"]),
    api_hash=os.environ["API_HASH"]
)

FORCE_SUB_LINKS = [
    "https://t.me/+27yPnr6aQYo2NDE1",
    "https://t.me/+udIcxtizerAwOTRl",
    "https://t.me/+np4is6JZyyY3MTg1",
    "https://t.me/+A0LsNrMLyX8yOGM1",
]

LINKS_FILE = "hourly_links.json"

def generate_random_hash():
    return ''.join(random.choices(string.hexdigits.lower(), k=64))

def load_links():
    if os.path.exists(LINKS_FILE):
        with open(LINKS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_links(links):
    with open(LINKS_FILE, "w") as f:
        json.dump(links, f)

def parse_hour(time_str):
    try:
        dt = datetime.strptime(time_str.lower(), "%I%p")
        return dt.hour
    except:
        return None

@Bot.on_message(filters.command("start") & filters.private)
async def start(bot, message):
    user_id = message.from_user.id
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id})

    buttons = [[InlineKeyboardButton("Join📣", url=url)] for url in FORCE_SUB_LINKS]
    buttons.append([InlineKeyboardButton("Verify✅", callback_data="verify")])
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply("**JOIN GIVEN CHANNEL TO GET REDEEM CODE**", reply_markup=reply_markup)

@Bot.on_callback_query(filters.regex("verify"))
async def verify_channels(bot, query):
    await query.message.delete()
    await query.message.reply(
        "📗 Welcome to NST free Google Play Redeem Code Bot RS30-200\n😍 Click On Generate Code 👾",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Generate Code", callback_data="gen_code")]])
    )

@Bot.on_callback_query(filters.regex("gen_code"))
async def generate_code(bot, query):
    config = config_collection.find_one({"_id": "config"}) or {}
    url = config.get("redeem_url", "https://modijiurl.com")
    hash_code = generate_random_hash()
    image_url = "https://envs.sh/CCn.jpg"

    caption = (
        "**Your Redeem Code Generated successfully✅ IF ANY PROBLEM CONTACT HERE @Paidpanelbot**\n\n"
        f"`hash:` `{hash_code}`\n"
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

@Bot.on_message(filters.command("setlink") & filters.private)
async def set_link(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized to use this command.")
    if len(message.command) < 2:
        return await message.reply("Usage: /setlink <url>")
    url = message.text.split(None, 1)[1]
    config_collection.update_one({"_id": "config"}, {"$set": {"redeem_url": url}}, upsert=True)
    await message.reply("Redeem link updated successfully.")

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

@Bot.on_message(filters.command("time") & filters.private)
async def set_hourly_links(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized to use this command.")
    
    lines = message.text.split("\n")[1:]  # skip the /time line
    links = {}
    for line in lines:
        try:
            time_str, url = line.strip().split()
            hour = parse_hour(time_str)
            if hour is not None:
                links[str(hour)] = url
        except:
            continue

    save_links(links)
    await message.reply("Hourly links have been set.")

async def send_hourly_links():
    while True:
        now = datetime.now(pytz.timezone("Asia/Kolkata"))
        current_hour = str(now.hour)
        links = load_links()
        if current_hour in links:
            try:
                await Bot.send_message(chat_id=CHANNEL_ID, text=f"Link for {now.strftime('%I:%M %p')} IST:\n{links[current_hour]}")
            except Exception as e:
                print(f"Error sending hourly link: {e}")
        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        await asyncio.sleep((next_hour - now).total_seconds())

# Health check server to prevent Koyeb sleep
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_server():
    server = HTTPServer(("0.0.0.0", 8080), HealthCheckHandler)
    server.serve_forever()

# Start health check server in background
threading.Thread(target=run_server).start()

# Run the bot and start hourly link task
async def main():
    await Bot.start()
    asyncio.create_task(send_hourly_links())
    from pyrogram.idle import idle
    await idle()

asyncio.run(main())
