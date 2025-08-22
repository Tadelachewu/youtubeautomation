import os
import json
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from pathlib import Path
from playwright.async_api import async_playwright

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_DATA_DIR = str(Path("nib_browser_profile").absolute())
CREDENTIALS_FILE = str(Path("nib_credentials.json").absolute())

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Playwright login ---
async def ensure_login(username: str, password: str, user_id: str):
    async with async_playwright() as p:
        # Use a **separate profile per user** to avoid conflicts
        user_profile_dir = Path(USER_DATA_DIR) / str(user_id)
        user_profile_dir.mkdir(parents=True, exist_ok=True)

        browser = await p.chromium.launch_persistent_context(
            str(user_profile_dir),
            headless=False
        )

        page = await browser.new_page()
        await page.goto("https://nibpmo.nibbank.com.et/login")

        try:
            if await page.get_by_role("link", name="My Tasks").is_visible():
                print(f"✅ User {user_id} already logged in")
            else:
                if username is None or password is None:
                    print(f"⚠️ User {user_id} needs credentials")
                    return False
                await page.get_by_role("textbox", name="Phone Number").fill(username)
                await page.get_by_role("textbox", name="Password").fill(password)
                await page.get_by_role("button", name="Sign In").click()
                await page.wait_for_load_state("networkidle")
                print(f"✅ User {user_id} logged in with provided credentials")
        except Exception as e:
            print(f"⚠️ Error checking login for user {user_id}: {e}")

        try:
            await page.get_by_role("link", name="My Tasks").click()
            await page.screenshot(path=f"logged_in_{user_id}.png")
        except:
            pass

        print(f"🟢 Browser for user {user_id} open for manual tasks")
        await asyncio.Event().wait()  # keep browser open

# --- Helper to manage multiple users ---
def save_credentials(user_id, phone, password):
    data = {}
    if Path(CREDENTIALS_FILE).exists():
        with open(CREDENTIALS_FILE, "r") as f:
            data = json.load(f)
    data[str(user_id)] = {"phone": phone, "password": password}
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(data, f)

def get_credentials(user_id):
    if not Path(CREDENTIALS_FILE).exists():
        return None
    with open(CREDENTIALS_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(user_id))

# --- Telegram bot commands ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    creds = get_credentials(user_id)
    if creds:
        await message.answer("✅ Found saved credentials. Opening browser automatically...")
        await ensure_login(creds["phone"], creds["password"], str(user_id))
    else:
        await message.answer(
            "👋 No saved credentials found. "
            "Please log in first using `/login phone password`"
        )

@dp.message(Command("login"))
async def login_handler(message: types.Message):
    try:
        _, phone, password = message.text.split()
        user_id = message.from_user.id
        save_credentials(user_id, phone, password)
        await message.answer("🔑 Credentials saved. Logging in...")
        await ensure_login(phone, password, str(user_id))
        await message.answer("✅ Browser opened. You can do your tasks manually.")
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

# --- Run bot ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
