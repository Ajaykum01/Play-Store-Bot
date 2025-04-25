import os
import threading
import random
import string
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from pyrogram.types import *
from pymongo import MongoClient
from dotenv import load_dotenv
import pytz
from datetime import datetime

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
    "https://t.me/+27yPnr6aQYo2NDE1",
    "https://t.me/+udIcxtizerAwOTRl",
    "https://t.me/+np4is6JZyyY3MTg1",
    "https://t.me/+A0LsNrMLyX8yOGM1"
]

async def is_user_subscribed(bot, user_id):
    for chat_id in FORCE_SUB_CHAT_IDS:
        try:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status in ("left", "kicked"):
                return False
        except:
            return False
    return True

def generate_random_hash():
    return ''.join(random.choices(string.hexdigits.lower(), k=64))

def get_current_hour_ist():
    tz = pytz.timezone('Asia/Kolkata')
    now = datetime.now(tz)
    hour = now.strftime("%-I%p").lower()  # eg: 6am, 7pm
    return hour

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
        "\ud83d\udcda Welcome to NST free Google Play Redeem Code Bot RS30-200\n\ud83d\ude0d Click On Generate Code \ud83d\udcc0",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Generate Code", callback_data="gen_code")]])
    )

@Bot.on_callback_query(filters.regex("verify"))
async def verify_channels(bot, query):
    user_id = query.from_user.id
    if await is_user_subscribed(bot, user_id):
        await query.message.delete()
        await query.message.reply(
            "\ud83d\udcda You’re Verified!\nClick Below to Generate Code.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Generate Code", callback_data="gen_code")]])
        )
    else:
        buttons = [[InlineKeyboardButton("Join Channel", url=url)] for url in FORCE_SUB_LINKS]
        buttons.append([InlineKeyboardButton("Verify✅", callback_data="verify")])
        await query.message.reply("**You're still missing one or more channels. Join all and press Verify again.**", reply_markup=InlineKeyboardMarkup(buttons))

@Bot.on_callback_query(filters.regex("gen_code"))
async def generate_code(bot, query):
    user_id = query.from_user.id
    if not await is_user_subscribed(bot, user_id):
        buttons = [[InlineKeyboardButton("Join Channel", url=url)] for url in FORCE_SUB_LINKS]
        buttons.append([InlineKeyboardButton("Verify✅", callback_data="verify")])
        return await query.message.reply("**You left a required channel. Please rejoin and press Verify.**", reply_markup=InlineKeyboardMarkup(buttons))

    config = config_collection.find_one({"_id": "config"}) or {}
    default_url = config.get("redeem_url", "https://modijiurl.com")
    hourly_links = config.get("hourly_links", {})

    current_hour = get_current_hour_ist()
    url = hourly_links.get(current_hour, default_url)

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
    await message.reply("Default redeem link updated successfully.")

@Bot.on_message(filters.command("time") & filters.private)
async def set_time_links(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized to use this command.")
    parts = message.text.split()
    if len(parts) < 3:
        return await message.reply("Usage: /time 6am https://link 7am https://link ...")

    time_links = {}
    i = 1
    while i < len(parts) - 1:
        time = parts[i].lower()
        link = parts[i + 1]
        time_links[time] = link
        i += 2

    config_collection.update_one({"_id": "config"}, {"$set": {"hourly_links": time_links}}, upsert=True)
    await message.reply("Hourly links updated successfully!")

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

def run_server():
    server = HTTPServer(("0.0.0.0", 8080), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_server).start()

Bot.run()
