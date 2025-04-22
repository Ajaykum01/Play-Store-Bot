import os
import play_scraper
from pyrogram import Client, filters
from pyrogram.types import *
from pyrogram.errors import UserNotParticipant, FloodWait
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

FORCE_SUB_CHANNELS = [
    {"link": "https://t.me/+27yPnr6aQYo2NDE1", "chat_id": -1002211067746},
    {"link": "https://t.me/+udIcxtizerAwOTRl", "chat_id": -1002010768345},
    {"link": "https://t.me/+np4is6JZyyY3MTg1", "chat_id": -1002168359986},
    {"link": "https://t.me/+A0LsNrMLyX8yOGM1", "chat_id": -1002096500701},
]

# MongoDB Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://leo2:leo2@cluster0.njkefn7.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
mongo_client = MongoClient(MONGO_URI)
db = mongo_client["PlayStoreBot"]
links_collection = db["user_links"]

broadcasted_users = set()

async def check_all_subs(client, message):
    not_joined = []
    for channel in FORCE_SUB_CHANNELS:
        try:
            user = await client.get_chat_member(channel["chat_id"], message.from_user.id)
            if user.status in ["kicked", "banned"]:
                await message.reply("You are banned from one of the required channels.")
                return False
        except UserNotParticipant:
            not_joined.append(channel["link"])

    if not_joined:
        buttons = [[InlineKeyboardButton("Join📣", url=link)] for link in not_joined]
        buttons.append([InlineKeyboardButton("Verify✅", callback_data="checksub")])
        await message.reply(
            "**Join all channels to use the bot:**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return False
    return True

@Bot.on_message(filters.command("setlink") & filters.private)
async def setlink(client, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply("You're not authorized to use this command.")

    if not await check_all_subs(client, message):
        return

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
    if not await check_all_subs(client, message):
        return

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
    if not await check_all_subs(bot, update):
        return
    text = "Search play store apps using below buttons.\n\nMade by @FayasNoushad"
    reply_markup = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text="Search here", switch_inline_query_current_chat="")],
            [InlineKeyboardButton(text="Search in another chat", switch_inline_query="")]
        ]
    )
    await update.reply_text(
        text=text,
        reply_markup=reply_markup,
        disable_web_page_preview=True,
        quote=True
    )

@Bot.on_inline_query()
async def search(bot, update):
    for channel in FORCE_SUB_CHANNELS:
        try:
            await bot.get_chat_member(channel["chat_id"], update.from_user.id)
        except UserNotParticipant:
            return

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
        if await check_all_subs(client, callback_query.message):
            await callback_query.message.edit("You are now verified! Send me the app name.")
        else:
            await callback_query.answer("You're still not subscribed to all channels.", show_alert=True)

# Run HTTP server (for Heroku uptime or similar)
def run_server():
    server = HTTPServer(("0.0.0.0", 8080), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_server).start()

# Start Bot
Bot.run()
