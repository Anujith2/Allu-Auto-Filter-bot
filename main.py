import time
import random
import string
import urllib.parse
import asyncio
import aiohttp
from aiohttp import web
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from info import (
    API_ID, API_HASH, BOT_TOKEN, ADMINS, 
    LOG_CHANNEL, DATABASE_CHANNEL, IS_VERIFY, 
    VERIFY_URL, VERIFY_API, HOW_TO_VERIFY, CHNL_LNK, URL
)

app = Client("my_telegram_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# In-Memory Storage
FILES_DB = {}       # {msg_id: {"file_name": name, "file_id": id, "file_size": size}}
VERIFIED_USERS = {} # {user_id: timestamp}
REDEEM_CODES = {}   # code: {"days": int, "max_users": int, "used_users": list}

# Dynamic Verification Link Generator using Linkshortify API
async def get_shortlink(long_url):
    api_url = f"https://{VERIFY_URL}/api?api={VERIFY_API}&url={urllib.parse.quote(long_url)}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                data = await response.json()
                if data.get("status") == "success":
                    return data.get("shortlink")
                return long_url
    except Exception as e:
        print(f"Shortlink API Error: {e}")
        return long_url

# --- 1. RENDER KEEP-ALIVE WEB SERVER ---

async def handle_ping(request):
    return web.Response(text="Bot is Live and Running!")

async def start_web_server():
    server = web.Application()
    server.router.add_get("/", handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

# --- 2. RELOAD OLD FILES FROM DATABASE CHANNEL ON STARTUP ---

async def load_old_database_files():
    print("🔄 Loading old files from Database Channel...")
    count = 0
    async for message in app.get_chat_history(DATABASE_CHANNEL, limit=2000):
        if message.document or message.video:
            media = message.document or message.video
            file_id = media.file_id
            file_name = media.file_name or message.caption or "Unknown File"
            file_size_mb = round(media.file_size / (1024 * 1024), 2)
            
            FILES_DB[message.id] = {
                "file_name": file_name,
                "file_id": file_id,
                "file_size": f"{file_size_mb} MB"
            }
            count += 1
    print(f"✅ Successfully loaded {count} old files into Bot memory!")

# --- 3. INDEX NEW FILES FROM DATABASE CHANNEL ---

@app.on_message(filters.chat(DATABASE_CHANNEL) & (filters.document | filters.video))
async def index_database_files(client, message):
    media = message.document or message.video
    file_id = media.file_id
    file_name = media.file_name or message.caption or "Unknown File"
    file_size_mb = round(media.file_size / (1024 * 1024), 2)
    
    FILES_DB[message.id] = {
        "file_name": file_name,
        "file_id": file_id,
        "file_size": f"{file_size_mb} MB"
    }

# --- 4. START COMMAND & NEW USER LOGGING & VERIFICATION ---

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user = message.from_user
    current_time = time.time()
    bot_username = (await client.get_me()).username
    
    # Send Start Log to Log Channel
    if len(message.command) == 1:
        log_text = (
            f"🚨 <b>#NEW_USER_STARTED</b>\n\n"
            f"👤 <b>Name:</b> {user.first_name} {user.last_name or ''}\n"
            f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
            f"🌐 <b>Username:</b> @{user.username if user.username else 'None'}"
        )
        try:
            await client.send_message(chat_id=LOG_CHANNEL, text=log_text)
        except Exception as e:
            print(f"Log Error: {e}")

    # Handling Deep Linking Requests (/start msg_id or verify payload)
    if len(message.command) > 1:
        payload = message.command[1]

        # Handle Verification Callback Completion
        if payload.startswith("verify_"):
            VERIFIED_USERS[user.id] = current_time + 86400  # 24 Hours Verification
            await message.reply_text("✅ <b>Verification Successful! You have 24 hours of unlimited access.</b>")
            return

        # 24 Hours Verification Check for Files
        if IS_VERIFY and user.id not in ADMINS:
            expiry_time = VERIFIED_USERS.get(user.id, 0)
            if current_time > expiry_time:
                # Generate Shortlink for Verification Completion
                verify_redirect_link = f"https://t.me/{bot_username}?start=verify_{user.id}"
                short_verify_link = await get_shortlink(verify_redirect_link)

                btn = [
                    [InlineKeyboardButton("Verify Now 🔐", url=short_verify_link)],
                    [InlineKeyboardButton("How To Verify ❓", url=HOW_TO_VERIFY)]
                ]
                await message.reply_text(
                    "⚠️ <b>You need to verify first to access files! Status lasts for 24 hours.</b>",
                    reply_markup=InlineKeyboardMarkup(btn)
                )
                return

        try:
            msg_id = int(payload)
            file_data = FILES_DB.get(msg_id)
            file_id = file_data["file_id"] if file_data else payload
            file_name = file_data["file_name"] if file_data else "Requested File"
        except ValueError:
            file_id = payload
            file_name = "Requested File"

        caption = (
            f"<b>{file_name}</b>\n\n"
            "<code>PLEASE FORWARD THIS FILES TO THE SAVED MESSAGE AND CLOSE THIS MESSAGE</code>"
        )
        
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 FAST DOWNLOAD / WATCH ONLINE 💻", callback_data=f"generate_links_{payload}")],
            [InlineKeyboardButton("📌 JOIN UPDATES CHANNEL 📌", url=CHNL_LNK)]
        ])
        
        if "video" in str(file_id):
            await message.reply_video(video=file_id, caption=caption, reply_markup=buttons)
        else:
            await message.reply_document(document=file_id, caption=caption, reply_markup=buttons)

        warning_txt = (
            "<b>❗ ❗ ❗ IMPORTANT ❗ ❗ ❗</b>\n\n"
            "<b>THIS MOVIE FILE/VIDEO WILL BE DELETED IN 5 MINUTE 😐 (DUE TO COPYRIGHT ISSUES).</b>\n\n"
            "<i>PLEASE FORWARD THIS FILE TO SOMEWHERE ELSE AND START DOWNLOADING THERE</i>"
        )
        await message.reply_text(warning_txt)
        return

    await message.reply_text(f"<b>HEY {user.first_name}, WELCOME TO BOT!</b>")

# --- 5. STREAM/DOWNLOAD LINK GENERATOR & LOG TRACKING ---

@app.on_callback_query(filters.regex(r"^generate_links_"))
async def generate_download_stream_links(client, callback_query: CallbackQuery):
    msg_id_str = callback_query.data.split("_")[2]
    user = callback_query.from_user
    
    try:
        msg_id = int(msg_id_str)
        file_info = FILES_DB.get(msg_id)
        file_name = file_info["file_name"] if file_info else "File.mkv"
    except Exception:
        file_name = "File.mkv"

    encoded_name = urllib.parse.quote(file_name)
    
    fast_download_url = f"{URL}/{msg_id_str}/{encoded_name}?hash=AgADwh"
    watch_online_url = f"{URL}/watch/{msg_id_str}/{encoded_name}?hash=AgADwh"

    link_buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Fast Download 🚀", url=fast_download_url),
            InlineKeyboardButton("💻 Watch online 💻", url=watch_online_url)
        ]
    ])

    await callback_query.message.reply_text(
        text=f"<b>{file_name}</b>\n\n<b>⚔️ LINK GENERATED ⚔️</b>",
        reply_markup=link_buttons,
        disable_web_page_preview=True
    )
    await callback_query.answer()

    # Log Stream/Download Usage
    stream_log = (
        f"📥 <b>#STREAM_DOWNLOAD_LOG</b>\n\n"
        f"👤 <b>User:</b> {user.first_name} ({user.mention})\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        f"🌐 <b>Username:</b> @{user.username if user.username else 'None'}\n"
        f"🎬 <b>Requested Show/File:</b>\n<code>{file_name}</code>"
    )
    try:
        await client.send_message(chat_id=LOG_CHANNEL, text=stream_log)
    except Exception as e:
        print(f"Log Error: {e}")

# --- 6. AUTO-FILTER IN GROUPS (REVERSE ORDER) ---

@app.on_message(filters.group & filters.text & ~filters.command(["start", "help"]))
async def auto_filter_group(client, message):
    start_time = time.time()
    query = message.text.strip().lower()
    
    matched_results = [(msg_id, data) for msg_id, data in FILES_DB.items() if query in data["file_name"].lower()]

    if not matched_results:
        return

    # Newest Episode First
    matched_results.reverse()

    total_files = len(matched_results)
    elapsed_time = round(time.time() - start_time, 2)
    bot_username = (await client.get_me()).username

    header_text = (
        f"<b><u>Anujith Bot 1</u></b>\n\n"
        f"<b>» TITLE :</b> {query}\n"
        f"<b>» TOTAL FILES :</b> {total_files}\n"
        f"<b>» REQUESTED BY :</b> {message.from_user.mention}\n"
        f"<b>» RESULT IN :</b> {elapsed_time} SECONDS\n\n"
        f"<b><i>» Requested Files 👇</i></b>\n"
    )

    buttons = []
    for msg_id, file in matched_results[:10]:
        btn_text = f"📂 {file['file_size']} ▷ {file['file_name']}"
        pm_link = f"https://t.me/{bot_username}?start={msg_id}"
        buttons.append([InlineKeyboardButton(btn_text, url=pm_link)])

    await message.reply_text(text=header_text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

# --- 7. PREMIUM CODE SYSTEM & EXPIRED LOGS ---

@app.on_message(filters.command("createcode") & filters.user(ADMINS))
async def create_code_cmd(client, message):
    if len(message.command) < 3:
        await message.reply_text("⚠️ <b>Usage:</b> <code>/createcode days users</code>")
        return
        
    days = int(message.command[1])
    max_users = int(message.command[2])
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    
    REDEEM_CODES[code] = {"days": days, "max_users": max_users, "used_users": []}
    await message.reply_text(f"✅ <b>Code Created:</b> <code>{code}</code>\n<b>Validity:</b> {days} Days\n<b>Limit:</b> {max_users} Users")

@app.on_message(filters.command("redeem"))
async def redeem_code_cmd(client, message):
    if len(message.command) < 2:
        await message.reply_text("⚠️ <b>Usage:</b> <code>/redeem CODE</code>")
        return

    code = message.command[1].strip()
    user = message.from_user
    
    if code not in REDEEM_CODES:
        await message.reply_text("❌ Invalid Redeem Code!")
        return
        
    code_data = REDEEM_CODES[code]
    
    if user.id in code_data["used_users"]:
        await message.reply_text("⚠️ You already redeemed this code!")
        return
        
    if len(code_data["used_users"]) >= code_data["max_users"]:
        await message.reply_text("❌ This Redeem Code has EXPIRED!")
        return

    code_data["used_users"].append(user.id)
    VERIFIED_USERS[user.id] = time.time() + (code_data["days"] * 86400 * 365) # Long Validity
    
    await message.reply_text(f"🎉 <b>Successfully Redeemed {code_data['days']} Days Premium!</b>")
    
    if len(code_data["used_users"]) >= code_data["max_users"]:
        expired_log = (
            f"⚠️ <b>#PREMIUM_CODE_EXPIRED</b>\n\n"
            f"🔑 <b>Code:</b> <code>{code}</code>\n"
            f"👥 <b>Total Users Used:</b> {len(code_data['used_users'])}/{code_data['max_users']}\n"
            f"📌 <b>Status:</b> All spots filled. Code is now Expired!"
        )
        try:
            await client.send_message(chat_id=LOG_CHANNEL, text=expired_log)
        except Exception as e:
            print(f"Log Error: {e}")

# --- 8. BOT RUNNER WITH AUTOMATIC LOADING & SERVER ---

async def main():
    await app.start()
    await start_web_server()
    await load_old_database_files()
    print("🚀 Bot is running and initialized!")
    await app.idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
  
