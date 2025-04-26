import os
import threading
import random
import string
import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from pyrogram.types import *
from pymongo import MongoClient
from dotenv import load_dotenv

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
    "https://t.me/+27yPnr6aQYo2NDE1",
    "https://t.me/+udIcxtizerAwOTRl",
    "https://t.me/+np4is6JZyyY3MTg1",
    "https://t.me/+A0LsNrMLyX8yOGM1",
]

def generate_random_hash():
    return ''.join(random.choices(string.hexdigits.lower(), k=64))

@Bot.on_message(filters.command("start") & filters.private)
async def start(bot, message):
    user_id = message.from_user.id
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id})

    buttons = [[InlineKeyboardButton("Join❤️", url=url)] for url in FORCE_SUB_LINKS]
    buttons.append([InlineKeyboardButton("Verify✅", callback_data="verify")])
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply("**JOIN GIVEN CHANNELS TO GET REDEEM CODE**", reply_markup=reply_markup)

@Bot.on_callback_query(filters.regex("verify"))
async def verify_channels(bot, query):
    await query.message.delete()
    await query.message.reply(
        "ðŸ“š Welcome to NST free Google Play Redeem Code Bot RS30-200\nðŸ˜ Click On Generate Code ðŸ’¾",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Generate Code", callback_data="gen_code")]])
    )

@Bot.on_callback_query(filters.regex("gen_code"))
async def generate_code(bot, query):
    config = config_collection.find_one({"_id": "config"}) or {}

    # Get current IST time
    ist = datetime.datetime.now(pytz.timezone("Asia/Kolkata"))
    current_time_key = ist.strftime("%-I%p").lower()      # eg: "6am"
    current_time_full_key = ist.strftime("%-I:%M%p").lower()  # eg: "6:10am"

    times_links = config.get("times_links", {})

    # Find matching link
    url = times_links.get(current_time_full_key) or times_links.get(current_time_key) or config.get("redeem_url", "https://modijiurl.com")

    hash_code = generate_random_hash()
    image_url = "https://envs.sh/CCn.jpg"

    caption = (
        "**Your Redeem Code Generated successfully✅ YOU CAN GET FREE CODES EVERY 1 HOURS 💕 IF ANY PROBLEM CONTACT HERE @Paidpanelbot**\n\n"
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
    await message.reply("Default redeem link updated successfully.")

@Bot.on_message(filters.command("time") & filters.private)
async def set_time_link(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized to use this command.")
    if len(message.text.split()) < 3:
        return await message.reply("Usage: /time <time> <url>\nExample: `/time 6am https://example.com/6am`", quote=True)

    _, time_text, url = message.text.split(maxsplit=2)
    time_text = time_text.lower()

    # Save time-based link into MongoDB
    config = config_collection.find_one({"_id": "config"}) or {}
    times_links = config.get("times_links", {})
    times_links[time_text] = url
    config_collection.update_one({"_id": "config"}, {"$set": {"times_links": times_links}}, upsert=True)

    await message.reply(f"Successfully set link for **{time_text}** as:\n{url}")

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
