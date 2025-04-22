import os
import play_scraper
from pyrogram import Client, filters
from pyrogram.types import *
from pyrogram.errors import FloodWait
from pymongo import MongoClient
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer
import asyncio

# Telegram Bot Configuration
Bot = Client(
    "Play-Store-Bot",
    bot_token=os.environ["BOT_TOKEN"],
    api_id=int(os.environ["API_ID"]),
    api_hash=os.environ["API_HASH"]
)

OWNER_ID = int(os.environ.get("OWNER_ID", 2117119246))  # Replace with your Telegram ID

# Private "Request to Join" Channel Invite Links
FORCE_SUB_CHANNELS = [
    {"link": "https://t.me/+A0LsNrMLyX8yOGM1"},
    {"link": "https://t.me/+np4is6JZyyY3MTg1"},
    {"link": "https://t.me/+udIcxtizerAwOTRl"},
    {"link": "https://t.me/+27yPnr6aQYo2NDE1"},
]

# MongoDB Configuration
MONGO_URI = os.environ.get("MONGO_URI", "your_mongodb_uri_here")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["PlayStoreBot"]
links_collection = db["user_links"]

broadcasted_users = set()

# Manual Join Prompt (no membership check due to private invite links)
async def check_all_subs(client, message):
    buttons = [[InlineKeyboardButton("Join📣", url=ch["link"])] for ch in FORCE_SUB_CHANNELS]
    buttons.append([InlineKeyboardButton("Verify✅", callback_data="checksub")])
    await message.reply(
        "**Join all channels to use the bot:**\nAfter joining, click Verify.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return False  # Always prompt unless user clicks Verify

@Bot.on_message(filters.command("setlink") & filters.private)
async def setlink(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("You're not authorized to use this command.")

    if len(message.command) < 2:
        await message.reply("Usage: `/setlink <your_modijiurl.com_link>`", parse_mode="Markdown")
        return

    link = message.command[1]
    user_id = message.from_user.id

    links_collection.update_one(
        {"user_id": user_id},
        {"$set": {"link": link}},
        upsert=True
    )

    await message.reply("Your custom shortened link has been saved!")

@Bot.on_message(filters.command("gen") & filters.private)
async def gen(client, message):
    user_id = message.from_user.id
    data = links_collection.find_one({"user_id": user_id})

    if data and "link" in data:
        await message.reply(f"Here is your shortened link: {data['link']}")
    else:
        await message.reply("No link found! Use `/setlink <your_modijiurl.com_link>` to set one.", parse_mode="Markdown")

@Bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("You're not authorized to use this command.")
    
    if len(message.command) < 2:
        return await message.reply("Usage: `/broadcast Your message here`", parse_mode="Markdown")

    text = message.text.split(" ", 1)[1]
    sent = 0
    failed = 0

    async for user in Bot.get_dialogs():
        try:
            if user.chat.type == "private":
                await client.send_message(user.chat.id, text)
                sent += 1
                await asyncio.sleep(0.1)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except:
            failed += 1

    await message.reply(f"Broadcast completed!\n\n✅ Sent: {sent}\n❌ Failed: {failed}")

@Bot.on_message(filters.private & filters.all)
async def filter_all(bot, update):
    await check_all_subs(bot, update)

@Bot.on_inline_query()
async def search(bot, update):
    # skip check here since we can't verify joins
    results = play_scraper.search(update.query)
    answers = []

    for result in results:
        details = f"""
**{result['title']}**
{result['description']}
Rating: {result['score']}
[View on Play Store]({result['url']})
        """
        answers.append(
            InlineQueryResultArticle(
                title=result['title'],
                description=result['description'],
                url=result['url'],
                thumb_url=result['icon'],
                input_message_content=InputTextMessageContent(details)
            )
        )

    await update.answer(answers, cache_time=1, is_personal=True)

@Bot.on_callback_query()
async def callback_query_handler(client, callback_query):
    if callback_query.data == "checksub":
        await callback_query.message.edit("✅ You're now verified! You can use the bot.")

# Run HTTP server (for uptime)
def run_server():
    server = HTTPServer(("0.0.0.0", 8080), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_server).start()

# Start the bot
Bot.run()
