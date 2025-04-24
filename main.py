import os
import threading
import random
import string
import pytz
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from pyrogram.types import *
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

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

FORCE_SUB_LINKS = [
    "https://t.me/+27yPnr6aQYo2NDE1",
    "https://t.me/+udIcxtizerAwOTRl",
    "https://t.me/+np4is6JZyyY3MTg1",
    "https://t.me/+A0LsNrMLyX8yOGM1",
]

CHANNEL_IDS = [
    -1002111111111,
    -1002222222222,
    -1002333333333,
    -1002444444444
]

def generate_random_hash():
    return ''.join(random.choices(string.hexdigits.lower(), k=64))

def get_current_hour_key():
    ist = pytz.timezone("Asia/Kolkata")
    hour = datetime.now(ist).strftime("%I%p").lstrip("0").lower()
    return hour

@Bot.on_message(filters.command("start") & filters.private)
async def start(bot, message):
    user_id = message.from_user.id
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id})

    all_joined = True
    for chat_id in CHANNEL_IDS:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status not in ("member", "administrator", "creator"):
                all_joined = False
                break
        except:
            all_joined = False
            break

    if not all_joined:
        buttons = [[InlineKeyboardButton("Join Channel", url=url)] for url in FORCE_SUB_LINKS]
        buttons.append([InlineKeyboardButton("Verify", callback_data="verify")])
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply("**JOIN ALL CHANNELS TO ACCESS BOT**", reply_markup=reply_markup)
        return

    await message.reply(
        "Welcome to the Redeem Code Bot! Click the button below to generate your code.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Generate Code", callback_data="gen_code")]])
    )

@Bot.on_callback_query(filters.regex("verify"))
async def verify_channels(bot, query):
    await start(bot, query.message)

@Bot.on_callback_query(filters.regex("gen_code"))
async def generate_code(bot, query):
    config = config_collection.find_one({"_id": "hourly_links"}) or {}
    hour_key = get_current_hour_key()
    url = config.get(hour_key, "https://modijiurl.com")
    hash_code = generate_random_hash()
    image_url = "https://envs.sh/CCn.jpg"

    caption = (
        "**Your Redeem Code Generated Successfully**\n\n"
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
async def set_hourly_links(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized to use this command.")

    text = message.text.split(None, 1)
    if len(text) < 2:
        return await message.reply("Usage: /time <hour> <url> [<hour> <url> ...]")

    parts = text[1].split()
    if len(parts) % 2 != 0:
        return await message.reply("Please provide hour-url pairs correctly.")

    links = dict(zip(parts[::2], parts[1::2]))
    config = config_collection.find_one({"_id": "hourly_links"}) or {}
    config.update(links)
    config_collection.update_one({"_id": "hourly_links"}, {"$set": config}, upsert=True)
    await message.reply("Hourly redeem links updated successfully.")

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

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_server():
    server = HTTPServer(("0.0.0.0", 8080), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_server).start()

Bot.run()
