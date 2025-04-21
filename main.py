import os
import play_scraper
from pyrogram import Client, filters
from pyrogram.types import *
from pyrogram.errors import UserNotParticipant

# Initialize the bot client
Bot = Client(
    "Play-Store-Bot",
    bot_token=os.environ["BOT_TOKEN"],
    api_id=int(os.environ["API_ID"]),
    api_hash=os.environ["API_HASH"]
)

# Specify the channel username (without @)
FORCE_SUB_CHANNEL = "YourChannelUsername"  # Replace with your channel's username

# Dictionary to store user-specific links
user_links = {}

# Function to check if the user is a member of the required channel
async def check_force_sub(client, message):
    try:
        user = await client.get_chat_member(FORCE_SUB_CHANNEL, message.from_user.id)
        if user.status in ["kicked", "banned"]:
            await message.reply("You are banned from using this bot.")
            return False
    except UserNotParticipant:
        try:
            invite_link = await client.create_chat_invite_link(FORCE_SUB_CHANNEL)
        except:
            invite_link = f"https://t.me/{FORCE_SUB_CHANNEL}"

        await message.reply(
            f"**To use this bot, you must join [this channel](https://t.me/{FORCE_SUB_CHANNEL}) first.**",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton("Join Channel", url=invite_link.invite_link if hasattr(invite_link, "invite_link") else invite_link),
                    InlineKeyboardButton("I've Joined", callback_data="checksub")
                ]]
            )
        )
        return False
    return True

# /setlink command
@Bot.on_message(filters.command("setlink") & filters.private)
async def setlink(client, message):
    if not await check_force_sub(client, message):
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
    user_id = message.from_user.id
    if user_id in user_links:
        await message.reply(f"Here is your shortened link: {user_links[user_id]}")
    else:
        await message.reply("No link found! Use `/setlink <your_modijiurl.com_link>` to set one.", parse_mode="Markdown")

# Handler for private messages
@Bot.on_message(filters.private & filters.all)
async def filter_all(bot, update):
    if not await check_force_sub(bot, update):
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

# Inline query handler
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

# Callback query handler for "I've Joined" button
@Bot.on_callback_query()
async def callback_query_handler(client, callback_query):
    if callback_query.data == "checksub":
        if await check_force_sub(client, callback_query.message):
            await callback_query.message.edit("You are now verified! Send me the app name.")
        else:
            await callback_query.answer("You're still not a member!", show_alert=True)

# Start the bot
Bot.run()
