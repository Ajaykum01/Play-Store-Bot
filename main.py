import os
import threading
import random
import string
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from pyrogram.types import *
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
import pytz

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

def get_force_sub_links():
    config = config_collection.find_one({"_id": "config"}) or {}
    return config.get("force_sub_links", [])

def generate_random_hash():
    return ''.join(random.choices(string.hexdigits.lower(), k=64))

def safe_text(text):
    return ''.join(c for c in text if not 0xD800 <= ord(c) <= 0xDFFF)

async def check_user_joined(bot, user_id):
    links = get_force_sub_links()
    for url in links:
        try:
            username = url.split("t.me/")[1].replace("+", "")
            member = await bot.get_chat_member(chat_id=username, user_id=user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except:
            return False
    return True

@Bot.on_message(filters.command("start") & filters.private)
async def start(bot, message):
    user_id = message.from_user.id
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id})

    if await check_user_joined(bot, user_id):
        await verify_channels(bot, message)
    else:
        buttons = [[InlineKeyboardButton(safe_text("Join📣"), url=url)] for url in get_force_sub_links()]
        buttons.append([InlineKeyboardButton(safe_text("Verify✅"), callback_data="verify")])
        reply_markup = InlineKeyboardMarkup(buttons)
        await message.reply("**JOIN GIVEN CHANNEL TO GET REDEEM CODE**", reply_markup=reply_markup)

@Bot.on_callback_query(filters.regex("verify"))
async def verify_channels(bot, query):
    if not await check_user_joined(bot, query.from_user.id):
        return await query.answer("Join all channels first!", show_alert=True)

    await query.message.delete()
    await query.message.reply(
        safe_text("📗 Welcome to NST free Google Play Redeem Code Bot RS30-200\n😍 Click On Generate Code 🔾"),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(safe_text("Generate Code"), callback_data="gen_code")]])
    )

@Bot.on_callback_query(filters.regex("gen_code"))
async def generate_code(bot, query):
    config = config_collection.find_one({"_id": "config"}) or {}
    ist = pytz.timezone("Asia/Kolkata")
    current_hour = datetime.now(ist).strftime("%-I%p").lower()
    hourly_links = config.get("hourly_links", {})
    url = hourly_links.get(current_hour, "https://modijiurl.com")
    hash_code = generate_random_hash()
    image_url = "https://envs.sh/CCn.jpg"

    caption = (
        safe_text("**Your Redeem Code Generated successfully✅ IF ANY PROBLEM CONTACT HERE @Paidpanelbot**\n\n") +
        f"`hash:` `{hash_code}`\n" +
        f"**Code :** `{url}`"
    )

    buttons = InlineKeyboardMarkup([[InlineKeyboardButton(safe_text("Generate Again"), callback_data="gen_code")]])

    await bot.send_photo(
        chat_id=query.message.chat.id,
        photo=image_url,
        caption=caption,
        reply_markup=buttons
    )
    await query.answer()

@Bot.on_message(filters.command("time") & filters.private)
async def set_hourly_link(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized.")
    text = message.text.split(None, 1)[1] if len(message.command) > 1 else ""
    if not text:
        return await message.reply("Usage: /time <hour> <url>\nExample: 6am https://link.com/6")
    try:
        hour, url = text.split(None, 1)
        config = config_collection.find_one({"_id": "config"}) or {}
        hourly_links = config.get("hourly_links", {})
        hourly_links[hour.lower()] = url
        config_collection.update_one({"_id": "config"}, {"$set": {"hourly_links": hourly_links}}, upsert=True)
        await message.reply(f"Time-based link for {hour} saved!")
    except:
        await message.reply("Invalid format. Use: /time <hour> <url>")

@Bot.on_message(filters.command("setchannels") & filters.private)
async def set_channels(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You're not authorized to set channels.")
    text = message.text.split(None, 1)[1] if len(message.command) > 1 else ""
    urls = text.split()
    if len(urls) < 1:
        return await message.reply("Usage: /setchannels <link1> <link2> ...")
    config_collection.update_one({"_id": "config"}, {"$set": {"force_sub_links": urls}}, upsert=True)
    await message.reply("Force subscription channels updated successfully.")

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
