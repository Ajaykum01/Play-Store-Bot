import os
import threading
import random
import string
import asyncio
import aiohttp
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
import pytz

load_dotenv()

# MongoDB setup
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
config_collection = db["config"]
users_collection = db["users"]

ADMINS = [int(i) for i in os.getenv("ADMINS", "2117119246").split()]

# Telegram Bot setup
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
    "https://t.me/+hXaGwny7nVo3NDM9"
]

# Cache for time-based links
time_links_cache = {}

def load_time_links():
    global time_links_cache
    config = config_collection.find_one({"_id": "time_links"}) or {}
    time_links_cache = config.get("links", {}) or {}

def parse_time_str(time_str):
    try:
        return datetime.strptime(time_str, "%I:%M%p").time()
    except:
        return datetime.strptime(time_str, "%I%p").time()

def get_current_link():
    if not time_links_cache:
        load_time_links()
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)
    current_time = now.time()

    sorted_times = sorted(time_links_cache.items(), key=lambda x: parse_time_str(x[0]))
    last_link = None
    for time_str, link in sorted_times:
        if current_time >= parse_time_str(time_str):
            last_link = link
        else:
            break
    return last_link or (sorted_times[-1][1] if sorted_times else "https://modijiurl.com")

# ---------------- START ----------------
@Bot.on_message(filters.command("start") & filters.private)
async def start(bot, message):
    user_id = message.from_user.id
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id})

    buttons = [[InlineKeyboardButton("Subscribe Channel ❤️", url=url)] for url in FORCE_SUB_LINKS]
    buttons.append([
        InlineKeyboardButton("Verify ✅", callback_data="verify"),
        InlineKeyboardButton("How to Verify ❓", url="https://t.me/kpslinkteam/52")
    ])
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply("**JOIN GIVEN CHANNEL TO GET REDEEM CODE**", reply_markup=reply_markup)

# ---------------- VERIFY ----------------
@Bot.on_callback_query(filters.regex("verify"))
async def verify_channels(bot, query):
    await query.message.delete()
    await query.message.reply(
        "🙏 Welcome to NST Free Google Play Redeem Code Bot RS30-200 🪙\nClick On Generate Code",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Generate Code", callback_data="gen_code")]
        ])
    )

# ---------------- GENERATE CODE ----------------
@Bot.on_callback_query(filters.regex("gen_code"))
async def generate_code(bot, query):
    buttons = [[InlineKeyboardButton("Subscribe Channel ❤️", url=url)] for url in FORCE_SUB_LINKS]
    buttons.append([
        InlineKeyboardButton("Verify ✅", callback_data="show_code"),
        InlineKeyboardButton("How to Verify ❓", url="https://t.me/kpslinkteam/52")
    ])
    reply_markup = InlineKeyboardMarkup(buttons)
    await query.message.reply("Before getting code, please verify again 👇", reply_markup=reply_markup)
    await query.answer()

# ---------------- SHOW CODE ----------------
@Bot.on_callback_query(filters.regex("show_code"))
async def show_code(bot, query):
    link = get_current_link()
    image_url = "https://envs.sh/CCn.jpg"

    caption = (
        "**Your Redeem Code Generated successfully ✅**\n"
        "✅ EVERY 1 HOURS YOU GET FREE CODES 💕\n"
        "❓ IF ANY PROBLEM CONTACT HERE: @Paidpanelbot\n\n"
        f"🔗 **Code:** [Click Me To Get Redeem Code]({link})\n\n"
        "📌 **How to open link:** https://t.me/kpslinkteam/52"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Generate Again 🔄", callback_data="gen_code")]
    ])

    await bot.send_photo(
        chat_id=query.message.chat.id,
        photo=image_url,
        caption=caption,
        reply_markup=buttons
    )
    await query.answer()

# ---------------- ADMIN COMMANDS ----------------
@Bot.on_message(filters.command("time") & filters.private)
async def set_time_links(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized.")
    try:
        text = message.text.split(None, 1)[1]
        lines = text.strip().splitlines()
        new_links = {}
        for line in lines:
            parts = line.strip().split(None, 1)
            if len(parts) != 2:
                return await message.reply("Invalid format. Use:\n`6:00am https://link.com`")
            time_str, url = parts
            parse_time_str(time_str.lower())
            new_links[time_str.lower()] = url
        config_collection.update_one({"_id": "time_links"}, {"$set": {"links": new_links}}, upsert=True)
        load_time_links()
        await message.reply(f"✅ Time links updated successfully!\n\nTotal {len(new_links)} timings set.")
    except Exception:
        await message.reply("Usage:\n/time\n6:00am https://link1.com\n6:30am https://link2.com")

@Bot.on_message(filters.command("setlink") & filters.private)
async def set_link(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized.")
    if len(message.command) < 2:
        return await message.reply("Usage: /setlink <url>")
    url = message.text.split(None, 1)[1]
    config_collection.update_one({"_id": "config"}, {"$set": {"redeem_url": url}}, upsert=True)
    await message.reply("Default redeem link updated successfully.")

@Bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized.")
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

# ---------------- HEALTH CHECK ----------------
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

# ---------------- MAIN ----------------
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    load_time_links()
    loop = asyncio.get_event_loop()
    loop.create_task(auto_ping())
    Bot.run()
