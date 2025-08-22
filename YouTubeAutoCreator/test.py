import asyncio
import json
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright

COOKIE_FILE = Path("youtube_cookies.json")
USER_DATA_DIR = str(Path("chrome_user_data").absolute())
OUTPUT_DIR = Path("output")

async def youtube_login(email: Optional[str] = None, password: Optional[str] = None) -> bool:
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
        try:
            await page.goto("https://accounts.google.com/ServiceLogin?service=youtube", timeout=120000, wait_until="networkidle")

            if email and password:
                try:
                    await page.fill('input[type="email"]', email)
                    await page.click('button:has-text("Next")')
                    await page.wait_for_selector('input[type="password"]', timeout=10000)
                    await page.fill('input[type="password"]', password)
                    await page.click('button:has-text("Next")')
                except:
                    print("⚠️ Automated login failed. Please login manually.")

            print("Please complete any manual login in the browser window if needed.")
            await page.wait_for_selector("#avatar-btn", timeout=180000)
            print("✅ Login successful!")

            cookies = await browser.cookies()
            with open(COOKIE_FILE, "w") as f:
                json.dump(cookies, f)
            return True
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False
        finally:
            await browser.close()

async def upload_video(file_path: str, title: str, description: str = "", tags=None):
    tags = tags or []
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            channel="chrome",
            headless=False
        )
        page = await browser.new_page()
        try:
            # Open YouTube Studio
            await page.goto("https://studio.youtube.com", wait_until="networkidle")
            await page.wait_for_selector('tp-yt-paper-icon-button[aria-label="Create"]', timeout=60000)
            await page.click('tp-yt-paper-icon-button[aria-label="Create"]')

            # Click "Upload videos"
            await page.click('tp-yt-paper-item:has-text("Upload videos")', timeout=30000)

            # Upload file
            file_input = await page.query_selector('input[type="file"]')
            await file_input.set_input_files(file_path)

            # Fill title and description
            await page.wait_for_selector('input#title-textbox', timeout=30000)
            await page.fill('input#title-textbox', title)
            await page.fill('textarea#description-textarea', description)

            if tags:
                await page.click('tp-yt-paper-button[aria-label="Show more"]', timeout=5000)
                await page.fill('input#text-input', ','.join(tags))

            # Next 3 times
            for _ in range(3):
                await page.wait_for_selector('ytcp-button:has-text("Next")', timeout=15000)
                await page.click('ytcp-button:has-text("Next")')
                await asyncio.sleep(2)

            # Publish
            await page.wait_for_selector('ytcp-button:has-text("Publish")', timeout=15000)
            await page.click('ytcp-button:has-text("Publish")')
            await asyncio.sleep(5)
            print(f"✅ Video uploaded: {file_path}")

        except Exception as e:
            print(f"❌ Upload failed: {e}")
        finally:
            await browser.close()

async def create_post(text: str, link: Optional[str] = None):
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            channel="chrome",
            headless=False
        )
        page = await browser.new_page()
        try:
            await page.goto("https://www.youtube.com/", wait_until="networkidle")
            await page.wait_for_selector('tp-yt-paper-icon-button[aria-label="Create"]', timeout=60000)
            await page.click('tp-yt-paper-icon-button[aria-label="Create"]')

            # Click "Create post"
            await page.click('tp-yt-paper-item[test-id="create-post"]', timeout=30000)

            # Wait for dialog to appear
            await page.wait_for_selector('tp-yt-paper-dialog', timeout=15000)

            # Fill the post content
            await page.fill('div[contenteditable="true"]', text)

            if link:
                await page.fill('input[type="url"]', link)

            # Click Post button
            await page.click('ytcp-button:has-text("Post")')
            await asyncio.sleep(3)
            print("✅ Post created successfully!")

        except Exception as e:
            print(f"❌ Create post failed: {e}")
        finally:
            await browser.close()

async def upload_all_videos():
    if not OUTPUT_DIR.exists():
        print("⚠️ Output directory does not exist")
        return

    video_files = list(OUTPUT_DIR.glob("*.mp4"))
    if not video_files:
        print("⚠️ No videos found in output folder")
        return

    for video in video_files:
        await upload_video(
            str(video),
            title=video.stem,
            description=f"Automated upload of {video.stem}",
            tags=["AI", "Automation"]
        )

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", help="Google email")
    parser.add_argument("--password", help="Google password")
    parser.add_argument("--post", help="Create a YouTube post with text")
    args = parser.parse_args()

    if not COOKIE_FILE.exists():
        success = asyncio.run(youtube_login(args.email, args.password))
        if not success:
            print("❌ Login failed")
            exit(1)

    # Upload videos
    asyncio.run(upload_all_videos())

    # Create post if argument provided
    if args.post:
        asyncio.run(create_post(args.post))
