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

# ───────────────── MongoDB ───────────────── #
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
config_collection = db["config"]
users_collection = db["users"]
tokens_collection = db["tokens"]  # for verification tokens

ADMINS = [int(i) for i in os.getenv("ADMINS", "2117119246").split()]

# ───────────────── Bot ───────────────── #
Bot = Client(
    "Play-Store-Bot",
    bot_token=os.environ["BOT_TOKEN"],
    api_id=int(os.environ["API_ID"]),
    api_hash=os.environ["API_HASH"]
)

HOW_TO_VERIFY_URL = "https://t.me/kpslinkteam/52"
FORCE_SUB_LINKS = [
    "https://yt.openinapp.co/fatz4",
    "https://yt.openinapp.co/u4hem",
    "https://t.me/+JJdz2hyOVRYyNzE1",
    "https://t.me/+hXaGwny7nVo3NDM9",
]

# Your GyanLinks API token (from your message)
GYANLINKS_API = "4be71cae8f3aeabe56467793a0ee8f20e0906f3a"

# ───────────────── Time-based links ───────────────── #
time_links_cache = {}

def load_time_links():
    global time_links_cache
    config = config_collection.find_one({"_id": "time_links"}) or {}
    time_links_cache = config.get("links", {}) or {}

def parse_time_str(time_str: str):
    try:
        return datetime.strptime(time_str, "%I:%M%p").time()
    except:
        return datetime.strptime(time_str, "%I%p").time()

def get_current_link():
    if not time_links_cache:
        load_time_links()
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist).time()

    sorted_times = sorted(time_links_cache.items(), key=lambda x: parse_time_str(x[0]))
    last_link = None
    for time_str, link in sorted_times:
        if now >= parse_time_str(time_str):
            last_link = link
        else:
            break
    return last_link or (sorted_times[-1][1] if sorted_times else "https://modijiurl.com")

# ───────────────── Helpers ───────────────── #
def gen_token(n: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(random.choices(alphabet, k=n))

async def shorten_with_gyanlinks(long_url: str) -> str:
    # GyanLinks expects a fully qualified URL
    encoded_url = urllib.parse.quote_plus(long_url)
    api_url = f"https://gyanilinks.com/api?api={GYANLINKS_API}&url={encoded_url}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=20) as resp:
                text = (await resp.text()).strip()
                # GyanLinks returns empty text on error; ensure valid https URL
                if text.startswith("http"):
                    return text
                return ""  # signal failure
    except Exception:
        return ""

async def build_verify_link(bot: Client, token: str) -> str:
    me = await bot.get_me()
    deep_link = f"https://t.me/{me.username}?start=GL{token}"
    short = await shorten_with_gyanlinks(deep_link)
    # Fallback to deep link if shortener failed to avoid BUTTON_URL_INVALID
    return short or deep_link

def ensure_user(user_id: int):
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id})

# ───────────────── Handlers ───────────────── #
@Bot.on_message(filters.command("start") & filters.private)
async def start(bot, message):
    user_id = message.from_user.id
    ensure_user(user_id)

    # Handle deep-link payload: /start GL<token>
    if len(message.command) > 1:
        payload = message.command[1]
        if payload.startswith("GL"):
            token = payload[2:]
            tok = tokens_collection.find_one({"_id": token})
            if not tok:
                return await message.reply("⚠️ Token not found or expired. Tap **Generate Code** again.")

            if tok.get("user_id") != user_id:
                return await message.reply("⚠️ This verification link belongs to another account. Please generate your own.")

            if tok.get("used"):
                return await message.reply("ℹ️ This token is already verified. Tap **Generate Again** to start over.")

            # Show the dedicated Verify Now button
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Verify now by clicking me✅", callback_data=f"final_verify:{token}")]
            ])
            return await message.reply(
                "✅ Short link completed!\n\nTap the button below to complete verification.",
                reply_markup=btn
            )

    # Default welcome (no payload)
    buttons = [[InlineKeyboardButton("Subscribe Channel 😎", url=url)] for url in FORCE_SUB_LINKS]
    buttons.append([InlineKeyboardButton("Verify ✅", callback_data="verify")])
    await message.reply("**JOIN GIVEN CHANNEL TO GET REDEEM CODE**", reply_markup=InlineKeyboardMarkup(buttons))

@Bot.on_callback_query(filters.regex("^verify$"))
async def verify_channels(bot, query):
    await query.message.delete()
    await query.message.reply(
        "🙏 Welcome to NST Free Google Play Redeem Code Bot RS30-200 🪙\nClick **Generate Code** to start verification.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Generate Code", callback_data="gen_code")]])
    )

@Bot.on_callback_query(filters.regex("^gen_code$"))
async def generate_code(bot, query):
    user_id = query.from_user.id
    ensure_user(user_id)

    # Create a pending token bound to this user
    token = gen_token()
    tokens_collection.insert_one({
        "_id": token,
        "user_id": user_id,
        "used": False,
        "created_at": datetime.utcnow()
    })

    # Build the verification link (goes through GyanLinks → redirects back to bot deep link)
    verify_url = await build_verify_link(bot, token)

    # Show ONLY "Verify (gyanlinks)" and "How to verify"
    caption = (
        "🔐 **Verification Required**\n\n"
        "1) Tap **Verify (gyanlinks)** and complete the steps.\n"
        "2) When you press **Get Link** there, you'll return here automatically.\n"
        "3) Then you'll get a button **“Verify now by clicking me✅”**."
    )
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Verify 🙂", url=verify_url)],
        [InlineKeyboardButton("How to verify ❓", url=HOW_TO_VERIFY_URL)],
    ])

    try:
        await query.message.delete()
    except Exception:
        pass

    await bot.send_message(user_id, caption, reply_markup=buttons, disable_web_page_preview=True)
    await query.answer()

@Bot.on_callback_query(filters.regex(r"^final_verify:(.+)$"))
async def final_verify(bot, query):
    user_id = query.from_user.id
    token = query.data.split(":", 1)[1]

    tok = tokens_collection.find_one({"_id": token})
    if not tok:
        return await query.answer("Token not found or expired.", show_alert=True)

    if tok.get("user_id") != user_id:
        return await query.answer("This token belongs to another account.", show_alert=True)

    if tok.get("used"):
        return await query.answer("Token already verified. Use Generate Again.", show_alert=True)

    # Mark token used
    tokens_collection.update_one({"_id": token}, {"$set": {"used": True, "used_at": datetime.utcnow()}})

    # Send the redeem link
    link = get_current_link()
    caption = (
    "✅ Verification Successful!\n\n"
    f"🎁 Redeem Code Link:- {link}\n\n"
    "🔄 You can generate again later."
    )
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Generate Again", callback_data="gen_code")]
    ])

    try:
        await query.message.delete()
    except Exception:
        pass

    await bot.send_message(user_id, caption, reply_markup=buttons, disable_web_page_preview=True)
    await query.answer("Verified ✅")

# ───────────────── Admin ───────────────── #
@Bot.on_message(filters.command("time") & filters.private)
async def set_time_links(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized to use this command.")
    try:
        text = message.text.split(None, 1)[1]
        lines = text.strip().splitlines()
        new_links = {}
        for line in lines:
            parts = line.strip().split(None, 1)
            if len(parts) != 2:
                return await message.reply("Invalid format. Use:\n`6:00am https://link.com`")
            time_str, url = parts
            parse_time_str(time_str.lower())  # validate
            new_links[time_str.lower()] = url
        config_collection.update_one({"_id": "time_links"}, {"$set": {"links": new_links}}, upsert=True)
        load_time_links()
        await message.reply(f"✅ Time links updated successfully!\n\nTotal {len(new_links)} timings set.")
    except Exception:
        await message.reply("Usage:\n/time\n6:00am https://link1.com\n6:30am https://link2.com")

@Bot.on_message(filters.command("setlink") & filters.private)
async def set_link(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("You are not authorized to use this command.")
    if len(message.command) < 2:
        return await message.reply("Usage: /setlink <url>")
    url = message.text.split(None, 1)[1]
    config_collection.update_one({"_id": "config"}, {"$set": {"redeem_url": url}}, upsert=True)
    await message.reply("Default redeem link updated successfully.")

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

# ───────────────── Health Check ───────────────── #
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_server():
    server = HTTPServer(("0.0.0.0", 8080), HealthCheckHandler)
    server.serve_forever()

# ───────────────── Main ───────────────── #
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    load_time_links()
    # Removed the old auto_ping that called Bot.start() (caused conflicts)
    Bot.run()
