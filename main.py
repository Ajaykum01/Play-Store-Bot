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
import time

load_dotenv()

# -------------------- CONFIG --------------------
MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL)
db = client["telegram_bot"]
users_collection = db["users"]
codes_collection = db["redeem_codes"]
tokens_collection = db["verify_tokens"]

ADMINS = [int(i) for i in os.getenv("ADMINS", "2117119246").split()]

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
    "https://t.me/+hXaGwny7nVo3NDM9",
]

GYANI_API_TOKEN = "4be71cae8f3aeabe56467793a0ee8f20e0906f3a"
VERIFY_PAGE_URL = "https://t.me/kpslinkteam/59"  # main verification
HOWTO_URL = "https://t.me/kpslinkteam/52"        # how to verify tutorial
CODE_IMAGE_URL = "https://envs.sh/CCn.jpg"


# -------------------- HELPERS --------------------
async def shorten_link(long_url: str) -> str:
    api_url = f"https://gyanilinks.com/api?api={GYANI_API_TOKEN}&url={long_url}&format=text"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=20) as resp:
                if resp.status == 200:
                    short = (await resp.text()).strip()
                    if short:
                        return short
    except:
        pass
    return long_url


def new_token(user_id: int) -> str:
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    tokens_collection.update_one(
        {"user_id": user_id},
        {"$set": {"token": token, "time": time.time(), "used": False}},
        upsert=True
    )
    return token


def check_token(user_id: int) -> bool:
    doc = tokens_collection.find_one({"user_id": user_id, "used": False})
    if not doc:
        return False
    # expire tokens after 5 minutes
    if time.time() - doc["time"] > 300:
        tokens_collection.delete_one({"_id": doc["_id"]})
        return False
    tokens_collection.update_one({"_id": doc["_id"]}, {"$set": {"used": True}})
    return True


def normalize_codes(raw: str):
    body = raw.split(maxsplit=1)
    if len(body) < 2:
        return []
    body = body[1]
    parts = re.split(r"[\s,]+", body)
    cleaned = []
    for p in parts:
        p = re.sub(r"[^\w\-]+$", "", p.strip())
        if re.fullmatch(r"[A-Za-z0-9\-_]+", p):
            cleaned.append(p)
    return cleaned


def get_fresh_code():
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

    # Generate token for this user
    token = new_token(query.from_user.id)
    verify_url = f"{VERIFY_PAGE_URL}?verify={token}"
    short_url = await shorten_link(verify_url)

    await query.message.reply(
        "⚠️ Please verify before generating your code.\n\n"
        "🔗 Open the verification link and complete it, then come back and press **I Verified**.",
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Verify Now", url=short_url)],
                [InlineKeyboardButton("ℹ️ How to Verify?", url=HOWTO_URL)],
                [InlineKeyboardButton("🔄 I Verified", callback_data="verified_generate")]
            ]
        )
    )


@Bot.on_callback_query(filters.regex("^verified_generate$"))
async def verified_generate(bot, query):
    user_id = query.from_user.id
    await query.message.delete()

    if not check_token(user_id):
        await query.message.reply(
            "❌ Verification failed or expired.\n\nPlease click **Generate Code** again and verify properly."
        )
        return

    code = get_fresh_code()
    if not code:
        await query.message.reply("⚠️ Sorry, no redeem codes left right now. Please try later.")
        return

    caption = (
        "**🎁 Your Redeem Code Generated successfully ✅**\n\n"
        f"🔗 **Code:** `{code}`\n\n"
        "📌 How to redeem: https://t.me/kpslinkteam/52\n\n"
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


# -------------------- ADMIN --------------------
@Bot.on_message(filters.command("codes") & filters.private)
async def add_codes(bot, message):
    if message.from_user.id not in ADMINS:
        return
    codes = normalize_codes(message.text)
    if not codes:
        return await message.reply("❌ Usage:\n/codes CODE1 CODE2 CODE3")
    inserted = 0
    for c in codes:
        if not codes_collection.find_one({"code": c}):
            codes_collection.insert_one({"code": c, "used": False})
            inserted += 1
    await message.reply(f"✅ Added {inserted} code(s).")


@Bot.on_message(filters.command("codes_left") & filters.private)
async def codes_left(bot, message):
    if message.from_user.id not in ADMINS:
        return
    left = codes_collection.count_documents({"used": {"$ne": True}})
    used = codes_collection.count_documents({"used": True})
    await message.reply(f"📦 Left: {left}\n🗂️ Used: {used}")
