import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright
from typing import Optional

FREEPIK_PROFILE_DIR = Path("freepik_profile")   # Persistent Chrome profile
FREEPIK_COOKIE_FILE = Path("freepik_cookies.json")

async def freepik_login(email: Optional[str] = None, password: Optional[str] = None) -> bool:
    async with async_playwright() as p:
        # ✅ Launch Chrome with persistent profile
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(FREEPIK_PROFILE_DIR),
            headless=False,
            channel="chrome",
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
            ],
        )

        page = await context.new_page()
        print("\n🌐 Navigating to Freepik login...")
        await page.goto("https://www.freepik.com/login", timeout=60000, wait_until="networkidle")

        # Cookie consent
        try:
            await page.click('button:has-text("Accept all cookies")', timeout=3000)
        except:
            pass

        manual_login = True
        if email and password:
            try:
                print("🔑 Attempting auto login...")

                # Step 1: Click "Continue with email"
                await page.click('button:has-text("Continue with email")', timeout=5000)

                # Step 2: Fill email
                await page.fill('input[type="email"]', email)
                await page.click('button:has-text("Continue")')

                # Step 3: Fill password
                await page.fill('input[type="password"]', password)
                await page.click('button:has-text("Log in"), button:has-text("Sign in")')

                manual_login = False
            except Exception as e:
                print(f"⚠️ Auto login failed: {e}")
                manual_login = True

        if manual_login:
            print("\n👉 Please log in manually in the opened Chrome window...")
            print("You have 3 minutes to finish login.")

        # ✅ Wait for successful login
        try:
            await asyncio.wait_for(
                page.wait_for_selector('a[href*="/logout"], img[alt*="Profile"]', state="attached"),
                timeout=180
            )
            print("✅ Login successful!")

            # Save cookies
            cookies = await context.cookies()
            with open(FREEPIK_COOKIE_FILE, "w") as f:
                json.dump(cookies, f, indent=2)
            print(f"🔐 Cookies saved to {FREEPIK_COOKIE_FILE.absolute()}")

            return True
        except asyncio.TimeoutError:
            print("❌ Login timeout - login not detected")
            return False
        finally:
            await context.close()

# Run standalone
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Freepik Login")
    parser.add_argument("--email", help="Freepik account email")
    parser.add_argument("--password", help="Freepik account password")
    args = parser.parse_args()

    success = asyncio.run(freepik_login(args.email, args.password))
    exit(0 if success else 1)
