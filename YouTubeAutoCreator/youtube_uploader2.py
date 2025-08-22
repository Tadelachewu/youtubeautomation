import asyncio
import json
import os
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright

COOKIE_FILE = Path("youtube_cookies.json")
USER_DATA_DIR = str(Path("chrome_user_data").absolute())  # persistent profile dir

async def youtube_login(email: Optional[str] = None, password: Optional[str] = None) -> bool:
    """Handles YouTube login either manually or with credentials and saves cookies."""
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                channel="chrome",
                headless=False,
                args=["--start-maximized", "--disable-blink-features=AutomationControlled", "--disable-infobars"]
            )
            page = await browser.new_page()
            await page.goto("https://accounts.google.com/ServiceLogin?service=youtube", timeout=60000, wait_until="networkidle")

            manual_login = False
            if email and password:
                try:
                    await page.fill('input[type="email"]', email)
                    await page.click('button:has-text("Next")')
                    await page.wait_for_selector('input[type="password"]', timeout=5000)
                    await page.fill('input[type="password"]', password)
                    await page.click('button:has-text("Next")')
                    try:
                        await page.wait_for_selector('text="This extra step shows it’s really you"', timeout=3000)
                        print("⚠️ 2FA required - please complete manually")
                        manual_login = True
                    except:
                        manual_login = False
                except Exception as e:
                    print(f"⚠️ Automated login failed: {e}")
                    manual_login = True
            else:
                manual_login = True

            if manual_login:
                print("\n👉 PLEASE MANUALLY LOGIN TO YOUTUBE NOW")
                print("You have 3 minutes to complete login...")

            try:
                await asyncio.wait_for(
                    asyncio.gather(
                        page.wait_for_selector("#avatar-btn", state="attached"),
                        page.wait_for_selector('yt-img-shadow.ytd-topbar-menu-button-renderer img', state="attached")
                    ),
                    timeout=180
                )
                print("\n✅ Login successful!")
                # Save cookies
                cookies = await browser.cookies()
                with open(COOKIE_FILE, "w") as f:
                    json.dump(cookies, f)
                return True
            except Exception as e:
                print(f"\n❌ Login detection failed: {str(e)}")
                return False
        finally:
            await browser.close()

async def check_cookies_valid() -> bool:
    """Check if saved cookies are still valid"""
    if not COOKIE_FILE.exists():
        return False
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            channel="chrome",
            headless=True
        )
        page = await browser.new_page()
        try:
            await page.goto("https://studio.youtube.com", timeout=30000)
            await page.wait_for_selector("#avatar-btn", timeout=10000)
            return True
        except:
            return False
        finally:
            await browser.close()

async def upload_video(video_path: str, title: str, description: str, tags: list[str] = None):
    """Upload video using persistent Chrome session (manual login once)."""
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            channel="chrome",
            headless=False,
            args=[
                "--start-maximized",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars"
            ]
        )
        page = await browser.new_page()

        # Go to YouTube Studio upload
        await page.goto("https://www.youtube.com/upload", wait_until="networkidle")
        
        # If not logged in, prompt manual login once
        if not await page.query_selector("#avatar-btn"):
            print("🔐 Not logged in — please log in manually.")
            await page.wait_for_selector("#avatar-btn", timeout=180000)
            print("✅ Login complete!")

        # Upload video file
        print(f"⏳ Uploading video: {video_path}")
        file_input = await page.wait_for_selector("input[type='file']", timeout=60000)
        await file_input.set_input_files(video_path)

        # Fill title
        title_box = await page.wait_for_selector("#title-textarea textarea", timeout=30000)
        await title_box.fill(title)

        # Fill description
        desc_box = await page.wait_for_selector("#description-textarea textarea", timeout=30000)
        await desc_box.fill(description)

        # Tags (optional)
        if tags:
            try:
                await page.click("#toggle-button", timeout=10000)
                tags_input = await page.wait_for_selector("#tags-container input", timeout=10000)
                await tags_input.fill(",".join(tags))
            except Exception as e:
                print(f"⚠️ Couldn't add tags: {e}")

        # Wait for processing (adjust if too long/short)
        await asyncio.sleep(90)

        # Click "Next" 3 times
        for _ in range(3):
            next_btn = await page.wait_for_selector("tp-yt-paper-button#next-button")
            await next_btn.click()
            await asyncio.sleep(2)

        # Set visibility to Public and publish
        public_btn = await page.wait_for_selector("tp-yt-paper-radio-button[name='PUBLIC']")
        await public_btn.click()

        publish_btn = await page.wait_for_selector("tp-yt-paper-button#done-button")
        await publish_btn.click()

        print(f"✅ Video uploaded successfully: {video_path}")
        await browser.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="YouTube Video Uploader")
    parser.add_argument("--video", required=True, help="Path to the video file")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--description", required=True, help="Video description")
    parser.add_argument("--tags", nargs="*", help="Optional tags")
    parser.add_argument("--email", help="Google account email", required=False)
    parser.add_argument("--password", help="Google account password", required=False)
    args = parser.parse_args()

    asyncio.run(upload_video(args.video, args.title, args.description, args.tags))
