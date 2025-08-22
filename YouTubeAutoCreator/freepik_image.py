import os
import re
import requests
from playwright.sync_api import sync_playwright, TimeoutError
from concurrent.futures import ThreadPoolExecutor, as_completed


def pollinations_generate_image(prompt, output_path):
    """Generate image using Pollinations API with caching & safe filenames."""
    max_len = 120
    base, ext = os.path.splitext(output_path)
    safe_base = re.sub(r'[^a-zA-Z0-9_]', '_', base)
    safe_base = safe_base[:max_len]
    output_path = safe_base + ext

    if os.path.exists(output_path):
        print(f"⚡ Cached Pollinations image found: {output_path}")
        return True

    outdir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(outdir, exist_ok=True)

    url = f"https://image.pollinations.ai/prompt/{prompt}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            print(f"✅ Pollinations image saved to {output_path}")
            return True
        else:
            print(f"❌ Pollinations API error: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Pollinations image generation error: {e}")
        return False


def generate_images_pollinations(prompts_outputs):
    """Batch generate multiple Pollinations images concurrently."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(pollinations_generate_image, prompt, output_path): (prompt, output_path)
            for prompt, output_path in prompts_outputs
        }
        for future in as_completed(futures):
            prompt, output_path = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"❌ Error generating {prompt}: {e}")


def generate_image(prompt, output_path, image_source_choice):
    """Unified image generator for Pollinations (2) or Freepik (1)."""
    if image_source_choice == "2":
        return pollinations_generate_image(prompt, output_path)

    # Default: Freepik AI (requires manual login)
    user_data_dir = "freepik_profile"
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(user_data_dir=user_data_dir, headless=False)
        page = browser.new_page()
        try:
            page.goto("https://www.freepik.com/pikaso/ai-image-generator", timeout=600000)
            input("👉 Please log in to Freepik in the opened browser window, then press Enter here to continue...")

            prompt_div = page.wait_for_selector('div[contenteditable="true"]', timeout=60000)
            prompt_div.fill(prompt)

            generate_btn = page.wait_for_selector(
                '//span[text()="Generate"]/ancestor::button | '
                '//span[text()="Generate"]/ancestor::div[contains(@class, "cursor-pointer")]',
                timeout=30000
            )
            generate_btn.click()

            page.wait_for_selector('img[src*="generated"]', timeout=120000)

            try:
                download_btn = page.wait_for_selector('button:has-text("Download")', timeout=30000)
                download_btn.click()
                print("✅ Freepik image generated (manual download may still be required).")
            except TimeoutError:
                print("⚠️ Download button not found. Manual download may still be required.")

        except TimeoutError:
            print("❌ Could not interact with Freepik page in time.")
        finally:
            browser.close()
