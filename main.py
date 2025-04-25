import os
import threading
import random
import string
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from pyrogram.types import *
from pymongo import MongoClient
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
from pytz import timezone
from dotenv import load_dotenv

load_dotenv()

# MongoDB setup
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
config_collection = db["config"]
users_collection = db["users"]

ADMINS = [int(i) for i in os.getenv("ADMINS", "2117119246").split()]

Bot = Client(
    "Play-Store-Bot",
    bot_token=os.environ["BOT_TOKEN"],
    api_id=int(os.environ["API_ID"]),
    api_hash=os.environ["API_HASH"]
)

FORCE_SUB_CHAT_IDS = [
    -1002211067746,
    -1002010768345,
    -1002168359986,
    -1002096500701
]

FORCE_SUB_LINKS = [
    "https://t.me/+JszZBjJEB4E5MmVl",
    "https://t.me/+udIcxtizerAwOTRl",
    "https://t.me/+np4is6JZyyY3MTg1",
    "https://t.me/+A0LsNrMLyX8yOGM1"
]

async def is_user_subscribed(bot, user_id):
    for chat_id in FORCE_SUB_CHAT_IDS:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

def generate_random_hash():
    return ''.join(random.choices(string.hexdigits.lower(), k=64))

def get_current_ist_key():
    ist = timezone("Asia/Kolkata")
    now = datetime.now(ist)
    return now.strftime("%-I:%M%p").lower()

def update_redeem_link():
    config = config_collection.find_one({"_id": "timed_links"}) or {}
    current_key = get_current_ist_key()
    fallback = config.get("6am")  # fallback to 6am if current not found
    link = config.get(current_key, fallback)
    config_collection.update_one({"_id": "config"}, {"$set": {"redeem_url": link}}, upsert=True)

scheduler = BackgroundScheduler()
scheduler.add_job(update_redeem_link, 'interval', minutes=1)
scheduler.start()

@Bot.on_message(filters.command("start") & filters.private)
async def start(bot, message):
    user_id = message.from_user.id
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id})

    if not await is_user_subscribed(bot, user_id):
        buttons = [[InlineKeyboardButton("Join Channel", url=url)] for url in FORCE_SUB_LINKS]
        buttons.append([InlineKeyboardButton("Verify✅", callback_data="verify")])
        return await message.reply("**JOIN GIVEN CHANNELS TO GET REDEEM CODE**", reply_markup=InlineKeyboardMarkup(buttons))

    await message.reply(
        "📚 Welcome to NST free Google Play Redeem Code Bot RS30-200\n😍 Click On Generate Code 💾",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Generate Code", callback_data="gen_code")]])
    )

@Bot.on_callback_query(filters.regex("verify"))
async def verify_channels(bot, query):
    user_id = query.from_user.id
    if await is_user_subscribed(bot, user_id):
        await query.message.delete()
        await query.message.reply(
            "📚 You’re Verified!\nClick Below to Generate Code.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Generate Code", callback_data="gen_code")]])
        )
    else:
        buttons = [[InlineKeyboardButton("Join Channel", url=url)] for url in FORCE_SUB_LINKS]
        buttons.append([InlineKeyboardButton("Verify✅", callback_data="verify")])
        await query.message.reply("You're still missing one or more channels. Join all and press Verify again.", reply_markup=InlineKeyboardMarkup(buttons))

@Bot.on_callback_query(filters.regex("gen_code"))
async def generate_code(bot, query):
    user_id = query.from_user.id
    if not await is_user_subscribed(bot, user_id):
        buttons = [[InlineKeyboardButton("Join Channel", url=url)] for url in FORCE_SUB_LINKS]
        buttons.append([InlineKeyboardButton("Verify✅", callback_data="verify")])
        return await query.message.reply("You left a required channel. Please rejoin and press Verify.", reply_markup=InlineKeyboardMarkup(buttons))

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

@Bot.on_message(filters.command("time") & filters.private)
async def set_time_links(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized to use this command.")
    if len(message.command) < 2:
        return await message.reply("Usage:\n/time <hour link pairs>\n\nExample:\n/time 6am https://link1 7am https://link2")

    raw = message.text.split(None, 1)[1]
    lines = raw.replace("\n", " ").split()
    if len(lines) % 2 != 0:
        return await message.reply("Invalid format. Each time should have a link.")

    data = {}
    for i in range(0, len(lines), 2):
        time_key = lines[i].strip().lower()
        link = lines[i + 1].strip()
        data[time_key] = link

    config_collection.update_one({"_id": "timed_links"}, {"$set": data}, upsert=True)
    update_redeem_link()
    await message.reply("Hourly links updated successfully.")

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

# Run the bot
Bot.run()
