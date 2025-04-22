import os
import play_scraper
from pyrogram import Client, filters
from pyrogram.types import *
from pyrogram.errors import UserNotParticipant
import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

# Initialize the bot client
Bot = Client(
    "Play-Store-Bot",
    bot_token=os.environ["BOT_TOKEN"],
    api_id=int(os.environ["API_ID"]),
    api_hash=os.environ["API_HASH"]
)

# Admin user ID
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

# Forced subscription channels
FORCE_CHANNELS = [
    {"chat_id": "freefirepannelfree", "link": "https://t.me/freefirepannelfree"},
    {"chat_id": "tamilmovierequestda", "link": "https://t.me/tamilmovierequestda"},
    {"chat_id": "+27yPnr6aQYo2NDE1", "link": "https://t.me/+_HZk2Yc4ug8xNTc9"},
    {"chat_id": "+_HZk2Yc4ug8xNTc9", "link": "https://t.me/+_HZk2Yc4ug8xNTc9"}
]

# User data
user_links = {}
user_db = set()

# Check if user is subscribed to all channels
async def check_force_sub(client, message):
    for channel in FORCE_CHANNELS:
        try:
            user = await client.get_chat_member(channel["chat_id"], message.from_user.id)
            if user.status in ["kicked", "banned"]:
                await message.reply("You are banned from using this bot.")
                return False
        except UserNotParticipant:
            await message.reply(
                f"**To use this bot, please join [this channel]({channel['link']}) first.**",
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("Join Channel", url=channel["link"]),
                    InlineKeyboardButton("I've Joined", callback_data="checksub")
                ]])
            )
            return False
    return True

# /setlink command (admin only)
@Bot.on_message(filters.command("setlink") & filters.private)
async def setlink(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("You are not authorized to use this command.")
        return
    if len(message.command) < 2:
        await message.reply("Usage: `/setlink <your_modijiurl.com_link>`", parse_mode="Markdown")
        return
    user_links[message.from_user.id] = message.command[1]
    await message.reply("Your custom shortened link has been saved!")

# /gen command
@Bot.on_message(filters.command("gen") & filters.private)
async def gen(client, message):
    if not await check_force_sub(client, message):
        return
    user_db.add(message.from_user.id)
    user_id = message.from_user.id
    if user_id in user_links:
        await message.reply(f"Here is your shortened link: {user_links[user_id]}")
    else:
        await message.reply("No link found! Use `/setlink <your_modijiurl.com_link>` to set one.", parse_mode="Markdown")

# /broadcast command (admin only)
@Bot.on_message(filters.command("broadcast") & filters.private)
async def broadcast(client, message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("You're not allowed to broadcast.")
        return
    if len(message.command) < 2:
        await message.reply("Usage: `/broadcast Your message here`", parse_mode="Markdown")
        return
    text = message.text.split(" ", 1)[1]
    sent_count = 0
    failed_count = 0
    for user_id in list(user_db):
        try:
            await client.send_message(user_id, text)
            sent_count += 1
        except:
            failed_count += 1
    await message.reply(f"Broadcast complete.\nSuccess: {sent_count}\nFailed: {failed_count}")

# Handle private messages
@Bot.on_message(filters.private & filters.all)
async def filter_all(bot, update):
    if not await check_force_sub(bot, update):
        return
    user_db.add(update.from_user.id)
    text = "♥️HELLO FRIEND, PLEASE JOIN ALL CHANNELS BELOW TO USE THIS BOT:"
    keyboard = [[InlineKeyboardButton(f"CHANNEL {i+1}", url=ch["link"])] for i, ch in enumerate(FORCE_CHANNELS)]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.reply_text(text=text, reply_markup=reply_markup, disable_web_page_preview=True, quote=True)

# Inline search handler
@Bot.on_inline_query()
async def search(bot, update):
    if not await check_force_sub(bot, update):
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

# Callback handler
@Bot.on_callback_query()
async def callback_query_handler(client, callback_query):
    if callback_query.data == "checksub":
        if await check_force_sub(client, callback_query.message):
            await callback_query.message.edit("You are now verified! Send me the app name.")
        else:
            await callback_query.answer("You're still not a member!", show_alert=True)

# Dummy server for Koyeb health check
def run_server():
    server = HTTPServer(("0.0.0.0", 8080), SimpleHTTPRequestHandler)
    server.serve_forever()

threading.Thread(target=run_server).start()

# Start the bot
Bot.run()
