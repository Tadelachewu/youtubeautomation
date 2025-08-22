import json
from pathlib import Path
from playwright.sync_api import sync_playwright
#playwright codegen --load-storage=youtube_storage.json https://youtube.com on terminal
COOKIE_FILE = Path("youtube_cookies.json")
STORAGE_STATE_FILE = Path("youtube_storage.json")

def convert_cookies_to_storage_state():
    if not COOKIE_FILE.exists():
        print("❌ Cookies file not found!")
        return

    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        cookies = json.load(f)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="chrome")
        context = browser.new_context(viewport=None)

        # Add cookies to the context
        context.add_cookies(cookies)

        # Save storage state for Playwright codegen
        context.storage_state(path=str(STORAGE_STATE_FILE))
        print(f"✅ Storage state saved to {STORAGE_STATE_FILE}")

        browser.close()

if __name__ == "__main__":
    convert_cookies_to_storage_state()
