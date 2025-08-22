
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
import subprocess
import sys
import atexit
LOCK_FILE = Path("bot.lock")

def acquire_lock():
    if LOCK_FILE.exists():
        print("❌ Another instance of the bot is already running. Exiting.")
        sys.exit(1)
    LOCK_FILE.write_text(str(os.getpid()))
    atexit.register(release_lock)

def release_lock():
    if LOCK_FILE.exists():
        try:
            LOCK_FILE.unlink()
        except Exception:
            pass
import shutil
from collections import defaultdict

from main import VideoCreator  # Your VideoCreator module
from youtube_batch_upload import batch_upload  # Your batch upload function


load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # Keep admin for uploads
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Set this to your public HTTPS URL
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_FULL_URL = f"{WEBHOOK_URL}{WEBHOOK_PATH}" if WEBHOOK_URL else None

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
task_lock = asyncio.Lock()


BASE_OUTPUT_DIR = Path("output")
USER_STORAGE_DIR = Path("user_storage")
USER_STORAGE_DIR.mkdir(exist_ok=True)

# In-memory user session state
user_sessions = defaultdict(dict)  # user_id: {"email":..., "password":..., "storage_file":..., "cookie_file":...}



# ---------------- USER LOGIN & STORAGE ----------------
async def ensure_user_login_and_storage(user_id: int, email: str, password: str):
    """Run login and storage conversion for a specific user if needed"""
    cookie_file = USER_STORAGE_DIR / f"youtube_cookies_{user_id}.json"
    storage_file = USER_STORAGE_DIR / f"youtube_storage_{user_id}.json"
    user_sessions[user_id]["cookie_file"] = cookie_file
    user_sessions[user_id]["storage_file"] = storage_file
    user_sessions[user_id]["email"] = email
    user_sessions[user_id]["password"] = password

    if not storage_file.exists():
        # Use the venv Python executable
        venv_python = str(Path(sys.executable))
        # Step 1: run test.py for login & cookies
        args = [venv_python, "test.py", "--email", email, "--password", password]
        env = os.environ.copy()
        env["COOKIE_FILE"] = str(cookie_file)
        print(f"➡️ Running test.py for user {user_id} login with {venv_python} ...")
        result = subprocess.run(args, capture_output=True, text=True, env=env)
        print(result.stdout)
        if result.returncode != 0:
            print(result.stderr)
            raise RuntimeError("❌ test.py failed. Please check login manually.")

        # Step 2: run persistent_auth.py to convert cookies to storage
        args2 = [venv_python, "persistent_auth.py"]
        env2 = os.environ.copy()
        env2["COOKIE_FILE"] = str(cookie_file)
        env2["STORAGE_STATE_FILE"] = str(storage_file)
        print(f"➡️ Converting cookies to storage state for user {user_id} with {venv_python} ...")
        result2 = subprocess.run(args2, capture_output=True, text=True, env=env2)
        print(result2.stdout)
        if result2.returncode != 0:
            print(result2.stderr)
            raise RuntimeError("❌ persistent_auth.py failed. Check cookies file.")
        print(f"✅ Login and storage state ready for user {user_id}.")
    else:
        print(f"✅ Storage state exists for user {user_id}. Skipping login.")


# ---------------- BOT UTILITIES ----------------
def kb_image_source(topic: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Use Pollinations", callback_data=f"imgsrc:2:{topic}"),
            InlineKeyboardButton(text="Use Freepik", callback_data=f"imgsrc:1:{topic}")
        ]
    ])


def get_user_output_dir(user_id: int) -> Path:
    user_dir = BASE_OUTPUT_DIR / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


# ---------------- BOT COMMANDS ----------------

# Per-user login state
pending_login = {}

@dp.message(CommandStart())
async def start(m: Message):
    user_id = m.from_user.id
    if user_id not in user_sessions or not user_sessions[user_id].get("storage_file"):
        pending_login[user_id] = True
        await m.answer("👋 Welcome! Please send your Google email:")
    else:
        await m.answer(
            "👋 Hi! You are already authenticated.\n\nCommands:\n• /video <topic>\n• /upload (admin only)\n• /help"
        )

# Handle email/password input for login
@dp.message()
async def handle_login(m: Message):
    user_id = m.from_user.id
    if user_id in pending_login:
        if "email" not in user_sessions[user_id]:
            user_sessions[user_id]["email"] = m.text.strip()
            await m.answer("Please send your Google password:")
            return
        elif "password" not in user_sessions[user_id]:
            user_sessions[user_id]["password"] = m.text.strip()
            email = user_sessions[user_id]["email"]
            password = user_sessions[user_id]["password"]
            try:
                await m.answer("🔐 Logging in, please wait...")
                await ensure_user_login_and_storage(user_id, email, password)
                del pending_login[user_id]
                await m.answer("✅ Login successful! Now you can use /video <topic> or /upload.")
            except Exception as e:
                await m.answer(f"❌ Login failed: {e}\nPlease send your email again:")
                user_sessions[user_id] = {}
            return


@dp.message(Command("help"))
async def help_cmd(m: Message):
    await start(m)



@dp.message(Command("upload"))
async def upload_cmd(m: Message):
    user_id = m.from_user.id
    if ADMIN_CHAT_ID and str(user_id) != str(ADMIN_CHAT_ID):
        return await m.answer("🚫 Only admin can upload.")
    if user_id not in user_sessions or not user_sessions[user_id].get("storage_file"):
        return await m.answer("❗ Please authenticate first with /start.")
    await m.answer("📤 Starting batch upload from your output folder ...")
    async with task_lock:
        # Pass user-specific storage file if needed
        await batch_upload(storage_file=user_sessions[user_id]["storage_file"])
    await m.answer("✅ Upload finished.")



@dp.message(Command("video"))
async def video_cmd(m: Message):
    user_id = m.from_user.id
    if user_id not in user_sessions or not user_sessions[user_id].get("storage_file"):
        return await m.answer("❗ Please authenticate first with /start.")
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        return await m.answer("Provide a topic: `/video Why Python`", parse_mode="Markdown")
    topic = parts[1].strip()
    await m.answer(
        f"📝 Topic received:\n<b>{topic}</b>\nChoose image source:",
        parse_mode="HTML",
        reply_markup=kb_image_source(topic)
    )



@dp.callback_query(F.data.startswith("imgsrc:"))
async def on_image_source(cb: CallbackQuery):
    user_id = cb.from_user.id
    if user_id not in user_sessions or not user_sessions[user_id].get("storage_file"):
        return await cb.message.answer("❗ Please authenticate first with /start.")
    _, src, topic = cb.data.split(":", 2)
    user_dir = get_user_output_dir(user_id)

    await cb.message.edit_text(
        f"✅ Image source selected: {'Pollinations' if src=='2' else 'Freepik'}\n🎬 Generating video for: <b>{topic}</b>...",
        parse_mode="HTML"
    )
    await cb.answer()

    creator = VideoCreator()
    loop = asyncio.get_event_loop()

    # Force image source choice from bot selection
    try:
        # Pass user-specific storage file if needed
        video_path = await loop.run_in_executor(None, creator.create_video, topic, src)
        video_path = Path(video_path)
        target_path = user_dir / video_path.name
        shutil.move(str(video_path), target_path)
        video_path = target_path
    except Exception as e:
        return await cb.message.answer(f"❌ Video generation failed: {e}")

    # Send video
    if video_path.stat().st_size < 50 * 1024 * 1024:
        await cb.message.answer_video(open(video_path, "rb"), caption=f"🎉 {video_path.name}", supports_streaming=True)
    else:
        await cb.message.answer(f"🎉 Video ready! Too large to send via Telegram.\nDownload: {video_path}", parse_mode="HTML")


# ---------------- START BOT ----------------


async def on_startup(bot):
    if WEBHOOK_FULL_URL:
        await bot.set_webhook(WEBHOOK_FULL_URL)
        print(f"✅ Webhook set: {WEBHOOK_FULL_URL}")
    else:
        print("⚠️ WEBHOOK_URL not set. Bot will not receive updates.")

async def on_shutdown(bot):
    if WEBHOOK_FULL_URL:
        await bot.delete_webhook()
        print("🛑 Webhook deleted.")

async def main():
    print("🤖 Bot started.")
    if WEBHOOK_FULL_URL:
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        from aiohttp import web

        app = web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
        setup_application(app, dp, bot=bot)
        await bot.set_webhook(WEBHOOK_FULL_URL)
        print(f"✅ Webhook set: {WEBHOOK_FULL_URL}")
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8080)
        print("🌐 Webhook server running on port 8080...")
        await site.start()
        while True:
            await asyncio.sleep(3600)
    else:
        await dp.start_polling(bot)


if __name__ == "__main__":
    acquire_lock()
    try:
        asyncio.run(main())
    finally:
        release_lock()


@dp.callback_query(F.data.startswith("imgsrc:"))
async def on_image_source(cb: CallbackQuery):
    _, src, topic = cb.data.split(":", 2)
    source_name = "Pollinations" if src == "2" else "Freepik"
    await cb.message.edit_text(
        f"✅ Image source selected: {source_name}\n🎬 Generating video for: <b>{topic}</b>\nThis may take a few minutes...",
        parse_mode="HTML"
    )
    await cb.answer()

    creator = VideoCreator()
    loop = asyncio.get_event_loop()
    # Run the create_video function in a thread to keep bot responsive
    # Updated: pass `src` if your create_video supports it
    try:
        video_path = await loop.run_in_executor(None, creator.create_video, topic, src)
    except TypeError:
        # fallback if create_video doesn't accept src
        video_path = await loop.run_in_executor(None, creator.create_video, topic)

    if not video_path or not Path(video_path).exists():
        return await cb.message.answer("❌ Video generation failed.")

    try:
        await cb.message.answer_video(open(video_path, "rb"), caption=f"🎉 {Path(video_path).name}")
    except Exception:
        await cb.message.answer(f"🎉 Video created: <code>{video_path}</code>", parse_mode="HTML")

    await cb.message.answer("📤 Uploading to YouTube...")
    async with task_lock:
        await batch_upload()
    await cb.message.answer("✅ Upload complete.")
    Path(video_path).unlink(missing_ok=True)


# ---------------- START BOT ----------------
async def main():
    await ensure_login_and_storage()
    print("🤖 Bot started.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
