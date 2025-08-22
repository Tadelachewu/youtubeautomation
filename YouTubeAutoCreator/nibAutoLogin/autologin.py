import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from playwright.async_api import async_playwright
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # set in environment
STORAGE_FILE = "nib_login_state.json"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Playwright login using your selectors ---
async def ensure_login(username: str, password: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        if os.path.exists(STORAGE_FILE):
            context = await browser.new_context(storage_state=STORAGE_FILE)
        else:
            context = await browser.new_context()

        page = await context.new_page()
        await page.goto("https://nibpmo.nibbank.com.et/login")

        if not os.path.exists(STORAGE_FILE):  # first time login
            # Fill credentials using scraped selectors
            await page.get_by_role("textbox", name="Phone Number").fill(username)
            await page.get_by_role("textbox", name="Password").fill(password)
            await page.get_by_role("button", name="Sign In").click()
            await page.wait_for_load_state("networkidle")
            await context.storage_state(path=STORAGE_FILE)  # save session
            print("✅ Session saved")

        # Example: navigate after login
        await page.get_by_role("link", name="My Tasks").click()
        await page.screenshot(path="logged_in.png")

        await browser.close()

# --- Telegram bot commands ---
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.answer("👋 Welcome! Send your credentials like:\n`/login phone password`")

@dp.message(Command("login"))
async def login_handler(message: types.Message):
    try:
        _, username, password = message.text.split()
        await message.answer("🔑 Logging in, please wait...")
        await ensure_login(username, password)
        await message.answer("✅ Logged in successfully! Session saved.")
    except Exception as e:
        await message.answer(f"❌ Error: {str(e)}")

# Run bot
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
