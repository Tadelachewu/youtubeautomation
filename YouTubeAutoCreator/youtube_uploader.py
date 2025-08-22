import asyncio
import json
import os
from pathlib import Path
from typing import Optional, List
from playwright.async_api import async_playwright, Page, BrowserContext

COOKIE_FILE = Path("youtube_cookies.json")
USER_DATA_DIR = Path("chrome_user_data").absolute()


async def launch_browser(headless=False) -> BrowserContext:
    """Launch persistent Chromium with user profile."""
    async with async_playwright() as p:
        return await p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            channel="chrome",
            headless=headless,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled", "--disable-infobars"]
        )


async def youtube_login(email: Optional[str] = None, password: Optional[str] = None) -> bool:
    """Login to YouTube (manual or automated) and save cookies."""
    browser = await launch_browser(headless=False)
    page = await browser.new_page()

    try:
        await page.goto("https://accounts.google.com/ServiceLogin?service=youtube", timeout=60000, wait_until="networkidle")
        manual_login = True

        if email and password:
            try:
                await page.fill('input[type="email"]', email)
                await page.click('button:has-text("Next")')
                await page.wait_for_selector('input[type="password"]', timeout=5000)
                await page.fill('input[type="password"]', password)
                await page.click('button:has-text("Next")')
                # Check for 2FA
                try:
                    await page.wait_for_selector('text="This extra step shows it’s really you"', timeout=3000)
                    print("⚠️ 2FA required — complete manually")
                except:
                    manual_login = False
            except Exception as e:
                print(f"⚠️ Automated login failed: {e}")

        if manual_login:
            print("\n👉 Please manually log in to YouTube now (3 minutes)...")
            await page.wait_for_selector("#avatar-btn", timeout=180000)

        # Save cookies
        cookies = await browser.cookies()
        with open(COOKIE_FILE, "w") as f:
            json.dump(cookies, f)
        print("✅ Login successful, cookies saved")
        return True

    except Exception as e:
        print(f"❌ Login failed: {e}")
        return False

    finally:
        await browser.close()


async def check_cookies_valid() -> bool:
    """Check if saved cookies are still valid."""
    if not COOKIE_FILE.exists():
        return False

    browser = await launch_browser(headless=True)
    page = await browser.new_page()
    try:
        await page.goto("https://studio.youtube.com", timeout=30000)
        await page.wait_for_selector("#avatar-btn", timeout=10000)
        return True
    except:
        return False
    finally:
        await browser.close()


async def upload_video(video_path: str, title: str, description: str, tags: Optional[List[str]] = None):
    """Upload a video to YouTube using persistent login."""
    browser = await launch_browser(headless=False)
    page = await browser.new_page()

    try:
        await page.goto("https://www.youtube.com/upload", wait_until="networkidle")

        # Wait for login if necessary
        if not await page.query_selector("#avatar-btn"):
            print("🔐 Not logged in — please log in manually.")
            await page.wait_for_selector("#avatar-btn", timeout=180000)
            print("✅ Login complete!")

        # Upload video
        print(f"⏳ Uploading video: {video_path}")
        file_input = await page.wait_for_selector("input[type='file']", timeout=60000)
        await file_input.set_input_files(video_path)

        # Fill title
        title_box = await page.wait_for_selector("#title-textarea textarea", timeout=30000)
        await title_box.fill(title)

        # Fill description
        desc_box = await page.wait_for_selector("#description-textarea textarea", timeout=30000)
        await desc_box.fill(description)

        # Add tags if provided
        if tags:
            try:
                await page.click("#toggle-button", timeout=10000)
                tags_input = await page.wait_for_selector("#tags-container input", timeout=10000)
                await tags_input.fill(",".join(tags))
            except Exception as e:
                print(f"⚠️ Couldn't add tags: {e}")

        # Wait for upload and processing (adjust timing)
        await asyncio.sleep(60)

        # Click "Next" 3 times
        for _ in range(3):
            next_btn = await page.wait_for_selector("tp-yt-paper-button#next-button")
            await next_btn.click()
            await asyncio.sleep(2)

        # Set Public and publish
        public_btn = await page.wait_for_selector("tp-yt-paper-radio-button[name='PUBLIC']")
        await public_btn.click()

        publish_btn = await page.wait_for_selector("tp-yt-paper-button#done-button")
        await publish_btn.click()

        print(f"✅ Video uploaded successfully: {video_path}")

    except Exception as e:
        print(f"❌ Upload failed: {e}")

    finally:
        await browser.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="YouTube Video Uploader")
    parser.add_argument("--video", required=True, help="Path to the video file")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--description", required=True, help="Video description")
    parser.add_argument("--tags", nargs="*", help="Optional tags")
    parser.add_argument("--email", help="Google account email")
    parser.add_argument("--password", help="Google account password")
    args = parser.parse_args()

    asyncio.run(upload_video(args.video, args.title, args.description, args.tags))
