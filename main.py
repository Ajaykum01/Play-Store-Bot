import os
import threading
import random
import string
import asyncio
import aiohttp
from http.server import BaseHTTPRequestHandler, HTTPServer
from pyrogram import Client, filters
from pyrogram.types import *
from pymongo import MongoClient
from dotenv import load_dotenv
import re

load_dotenv()

# -------------------- CONFIG --------------------
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
config_collection = db["config"]
users_collection = db["users"]
codes_collection = db["redeem_codes"]  # stores redeem codes

ADMINS = [int(i) for i in os.getenv("ADMINS", "2117119246").split()]

# Telegram Bot setup
Bot = Client(
    "Play-Store-Bot",
    bot_token=os.environ["BOT_TOKEN"],
    api_id=int(os.environ["API_ID"]),
    api_hash=os.environ["API_HASH"]
)

# Channels to join
FORCE_SUB_LINKS = [
    "https://yt.openinapp.co/fatz4",
    "https://yt.openinapp.co/u4hem",
    "https://t.me/+JJdz2hyOVRYyNzE1",
    "https://t.me/+hXaGwny7nVo3NDM9",
]

# GyaniLinks API for verification short link
GYANI_API_TOKEN = "4be71cae8f3aeabe56467793a0ee8f20e0906f3a"
VERIFY_TUTORIAL_URL = "https://t.me/kpslinkteam/59"

# Image shown with code
CODE_IMAGE_URL = "https://envs.sh/CCn.jpg"


# -------------------- HELPERS --------------------
async def shorten_link(long_url: str) -> str:
    """
    Shorten a link using GyaniLinks API (text format).
    Returns the short link if successful; otherwise returns the original link.
    """
    api_url = f"https://gyanilinks.com/api?api={GYANI_API_TOKEN}&url={long_url}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=20) as resp:
                if resp.status == 200:
                    short = (await resp.text()).strip()
                    if short:
                        return short
    except Exception as e:
        print("Shortener error:", e)
    return long_url


def normalize_codes(raw: str):
    """
    Parse /codes input like: '/codes Abc582 ,Bslei92. xyz-123'
    Returns a cleaned list of codes (alnum + - _ allowed).
    """
    # Remove the command itself
    body = raw.split(maxsplit=1)
    if len(body) < 2:
        return []
    body = body[1]

    # Split on whitespace or commas
    parts = re.split(r"[\s,]+", body)
    cleaned = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Strip trailing punctuation
        p = re.sub(r"[^\w\-]+$", "", p)
        # Allow only safe chars
        if re.fullmatch(r"[A-Za-z0-9\-_]+", p):
            cleaned.append(p)
    return cleaned


def get_fresh_code():
    """
    Atomically fetch the next unused code and mark as used.
    """
    doc = codes_collection.find_one_and_update(
        {"used": {"$ne": True}},
        {"$set": {"used": True}},
        sort=[("_id", 1)]
    )
    if doc:
        return doc.get("code")
    return None


# -------------------- USER FLOW --------------------
@Bot.on_message(filters.command("start") & filters.private)
async def start(bot, message):
    user_id = message.from_user.id
    if not users_collection.find_one({"_id": user_id}):
        users_collection.insert_one({"_id": user_id})

    buttons = [[InlineKeyboardButton("📢 Join Channel", url=url)] for url in FORCE_SUB_LINKS]
    buttons.append([InlineKeyboardButton("✅ I Joined", callback_data="joined")])

    await message.reply(
        "👋 Welcome!\n\nJoin all the channels below and then click **I Joined ✅** to continue.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@Bot.on_callback_query(filters.regex("^joined$"))
async def joined_channels(bot, query):
    await query.message.delete()
    await query.message.reply(
        "✅ Great! You joined all channels.\n\nClick below to generate your free redeem code 👇",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("🎁 Generate Code", callback_data="gen_code_verify")]]
        )
    )


@Bot.on_callback_query(filters.regex("^gen_code_verify$"))
async def gen_code_verify(bot, query):
    await query.message.delete()

    # Always shorten the verification tutorial link so it goes via your shortener
    short_verify_url = await shorten_link(VERIFY_TUTORIAL_URL)

    await query.message.reply(
        "⚠️ Due to high demand of redeem codes, please verify you're a real person before generating.\n\n"
        "📌 Watch the video and follow the steps in the verification page.",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Verify Now", url=short_verify_url)],
                [InlineKeyboardButton("🔄 After Verify, Click Here", callback_data="verified_generate")]
            ]
        )
    )


@Bot.on_callback_query(filters.regex("^verified_generate$"))
async def verified_generate(bot, query):
    await query.message.delete()

    code = get_fresh_code()
    if not code:
        await query.message.reply(
            "⚠️ Sorry, no redeem codes left right now. Please try again later."
        )
        return

    caption = (
        "**🎁 Your Redeem Code Generated successfully ✅**\n\n"
        f"🔗 **Code:** `{code}`\n\n"
        "📌 **How to redeem code:** https://t.me/kpslinkteam/52\n\n"
        "⏳ You can generate again, but must verify each time."
    )

    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔄 Generate Again", callback_data="gen_code_verify")]]
    )

    await bot.send_photo(
        chat_id=query.message.chat.id,
        photo=CODE_IMAGE_URL,
        caption=caption,
        reply_markup=buttons
    )
    await query.answer()


# -------------------- ADMIN COMMANDS --------------------
@Bot.on_message(filters.command("codes") & filters.private)
async def add_codes(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("❌ You are not authorized to use this command.")

    codes = normalize_codes(message.text)
    if not codes:
        return await message.reply("❌ Usage:\n`/codes CODE1 CODE2 CODE3`\nYou can also separate with commas.", quote=True)

    inserted = 0
    for c in codes:
        # Avoid duplicates if already present and unused
        existing = codes_collection.find_one({"code": c})
        if existing:
            continue
        codes_collection.insert_one({"code": c, "used": False})
        inserted += 1

    await message.reply(f"✅ Added {inserted} code(s).")


@Bot.on_message(filters.command("codes_left") & filters.private)
async def codes_left(bot, message):
    if message.from_user.id not in ADMINS:
        return await message.reply("❌ You are not authorized to use this command.")
    left = codes_collection.count_documents({"used": {"$ne": True}})
    used = codes_collection.count_documents({"used": True})
    await message.reply(f"📦 Codes left: {left}\n🗂️ Codes used: {used}")


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


# -------------------- HEALTH CHECK --------------------
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
    # If you host on a free service that sleeps, you can ping your own URL here.
    await Bot.start()
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                await session.get("https://jittery-merna-agnalagnal4-8c1a65b0.koyeb.app/")
        except:
            pass
        await asyncio.sleep(300)


# -------------------- MAIN --------------------
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    loop = asyncio.get_event_loop()
    loop.create_task(auto_ping())
    Bot.run()
