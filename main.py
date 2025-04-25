import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import UserNotParticipant
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

FORCE_SUB_LINKS = [
    os.environ.get("FORCE_SUB_LINK1"),
    os.environ.get("FORCE_SUB_LINK2"),
    os.environ.get("FORCE_SUB_LINK3"),
    os.environ.get("FORCE_SUB_LINK4"),
]

ADMINS = [int(x) for x in os.environ.get("ADMINS", "").split()]
Bot = Client("biisal-bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

logging.basicConfig(level=logging.INFO)

# Start a simple HTTP server for Koyeb health check
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    server = HTTPServer(('0.0.0.0', 8080), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# Force Sub Check (link-based, not channel ID)
async def is_user_joined(client, user_id):
    for link in FORCE_SUB_LINKS:
        if not link:
            continue
        try:
            invite_hash = link.split("+")[1]
            chat = await client.join_chat(f"https://t.me/+{invite_hash}")  # get Chat object
            member = await client.get_chat_member(chat.id, user_id)
            if member.status not in ("member", "administrator", "creator"):
                return False
        except UserNotParticipant:
            return False
        except Exception as e:
            logging.warning(f"Error checking user subscription: {e}")
            return False
    return True

@Bot.on_message(filters.private & filters.command("start"))
async def start_handler(client, message):
    user_id = message.from_user.id

    if await is_user_joined(client, user_id):
        await message.reply_text(
            "**Welcome! You're verified. Use the bot freely.**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Do Something", callback_data="do_action")]
            ])
        )
    else:
        buttons = [[InlineKeyboardButton(f"Join Channel {i+1}", url=link)]
                   for i, link in enumerate(FORCE_SUB_LINKS) if link]
        buttons.append([InlineKeyboardButton("✅ Joined All", callback_data="check_force_sub")])

        await message.reply_text(
            "**Please join all the channels below to use this bot:**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

@Bot.on_callback_query(filters.regex("check_force_sub"))
async def verify_handler(client, query):
    user_id = query.from_user.id
    if await is_user_joined(client, user_id):
        await query.message.edit("✅ Thank you! You’re now verified.")
    else:
        await query.answer("❗ Please join all required channels first.", show_alert=True)

# Optional example callback
@Bot.on_callback_query(filters.regex("do_action"))
async def do_action(client, query):
    await query.answer("This is just an example button.")

Bot.run()
