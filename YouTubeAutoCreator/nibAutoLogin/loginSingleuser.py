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
CREDENTIALS_FILE = str(Path("nib_credentials.json").absolute())  # store phone/password

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Playwright login with optional saved credentials ---
async def ensure_login(username: str = None, password: str = None):
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=False
        )
        page = await browser.new_page()
        await page.goto("https://nibpmo.nibbank.com.et/login")

        # If "My Tasks" link is visible → already logged in
        try:
            if await page.get_by_role("link", name="My Tasks").is_visible():
                print("✅ Already logged in, browser ready for tasks")
            else:
                # Fill credentials if provided (first time or expired session)
                if username is None or password is None:
                    print("⚠️ Credentials needed")
                    return False
                await page.get_by_role("textbox", name="Phone Number").fill(username)
                await page.get_by_role("textbox", name="Password").fill(password)
                await page.get_by_role("button", name="Sign In").click()
                await page.wait_for_load_state("networkidle")
                print("✅ Logged in with provided credentials")

        except Exception as e:
            print("⚠️ Error checking login:", e)

        # Navigate to My Tasks
        try:
            await page.get_by_role("link", name="My Tasks").click()
            await page.screenshot(path="logged_in.png")
        except:
            pass

        print("🟢 Browser is open for manual tasks")
        await asyncio.Event().wait()  # keep browser open

# --- Telegram commands ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    # Load saved credentials
    if Path(CREDENTIALS_FILE).exists():
        with open(CREDENTIALS_FILE, "r") as f:
            data = json.load(f)
        username = data.get("phone")
        password = data.get("password")
        await message.answer("✅ Found saved credentials. Opening browser...")
        await ensure_login(username, password)
    else:
        await message.answer(
            "👋 No saved credentials found. "
            "Please log in first using `/login phone password`"
        )

@dp.message(Command("login"))
async def login_handler(message: types.Message):
    try:
        _, username, password = message.text.split()
        # Save credentials for later
        with open(CREDENTIALS_FILE, "w") as f:
            json.dump({"phone": username, "password": password}, f)
        await message.answer("🔑 Credentials saved. Logging in...")
        await ensure_login(username, password)
        await message.answer("✅ Browser opened. You can do your tasks manually.")
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

# --- Run bot ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
