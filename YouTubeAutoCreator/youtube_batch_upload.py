import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

# -----------------------------
# Config
# -----------------------------
OUTPUT_DIR = Path("output")
USER_DATA_DIR = Path("chrome_user_data")  # Persistent profile with saved login

# -----------------------------
# Upload function
# -----------------------------
# -----------------------------
# Upload function
# -----------------------------
async def upload_video(video_path: str, title: str, description: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR.absolute()),
            channel="chrome",
            headless=False,
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"]
        )
        page = await browser.new_page()
        await page.goto("https://www.youtube.com/upload", wait_until="networkidle")
        await page.wait_for_timeout(3000)

        # Upload file
        file_input = page.locator("input[type='file']")
        await file_input.set_input_files(video_path)
        print(f"⏳ Uploading: {video_path} ...")

        # Fill title & description
        await page.get_by_role("textbox", name="Add a title that describes your video").fill(title)
        await page.get_by_role("textbox", name="Tell viewers about your video").fill(description)

        # Wait until overlay disappears, then set audience
        await page.wait_for_selector(".dialog-scrim", state="detached", timeout=60000)
        await page.get_by_role("radio", name="No, it's not 'Made for Kids'").check()

        # Click Next 3 times
        for _ in range(3):
            next_btn = page.get_by_role("button", name="Next")
            await next_btn.wait_for(state="visible", timeout=60000)
            await next_btn.click()
            await page.wait_for_timeout(2000)

        # Visibility = Public
        public_radio = page.get_by_role("radio", name="Public")
        await public_radio.wait_for(state="visible", timeout=60000)
        await public_radio.check()

        # Publish
        publish_btn = page.get_by_role("button", name="Publish")
        await publish_btn.wait_for(state="enabled", timeout=300000)
        await publish_btn.click()

        print(f"✅ Uploaded successfully: {video_path}")
        await browser.close()




# -----------------------------
# Batch upload
# -----------------------------
async def batch_upload():
    if not OUTPUT_DIR.exists():
        print("❌ Output folder not found")
        return

    videos = list(OUTPUT_DIR.glob("*.mp4"))
    if not videos:
        print("❌ No video files found in output folder")
        return

    for video in videos:
        title = video.stem.replace("_", " ")
        description = f"Automated upload for {title}"
        try:
            await upload_video(str(video), title, description)
        except Exception as e:
            print(f"❌ Failed to upload {video.name}: {e}")


# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    asyncio.run(batch_upload())
