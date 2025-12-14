#!/usr/bin/env python3
"""
Script to download Sardine School gallery images using browser automation.

Usage:
1. Run the script
2. Browser window will open showing the website
3. Manually scroll to the Sardine gallery and click the FIRST image
4. The script will automatically click through all images and download them
5. Press Ctrl+C when done or let it run until no more images
"""

import os
import time
import requests
from playwright.sync_api import sync_playwright
import re
import sys

OUTPUT_DIR = "sardine_school_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Set to False to see the browser (helpful for debugging)
HEADLESS = len(sys.argv) > 1 and sys.argv[1] == "--headless"

def download_image_from_url(url, filename):
    """Download an image from URL"""
    try:
        response = requests.get(url, timeout=30, stream=True)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"    Error downloading: {e}")
        return False

def get_original_image_url(img_src):
    """Extract the original quality image URL"""
    match = re.search(r'(https://static\.wixstatic\.com/media/dd09ca_[a-f0-9]+~mv2\.(jpg|jpeg|png))', img_src)
    if match:
        return match.group(1), match.group(2)
    return None, None

def main():
    print("="*70)
    print("Sardine School Gallery - Interactive Downloader")
    print("="*70)
    if not HEADLESS:
        print("\n📌 INSTRUCTIONS:")
        print("1. A browser window will open")
        print("2. Scroll down to the 'Sardine School Survival' gallery")
        print("3. Click on the FIRST image to open it")
        print("4. Wait - the script will auto-download all images!")
        print("\nWaiting 10 seconds before starting...\n")
        time.sleep(10)
    else:
        print("Running in headless mode...")

    with sync_playwright() as p:
        print(f"\nLaunching browser ({'headless' if HEADLESS else 'visible'})...")
        browser = p.chromium.launch(headless=HEADLESS)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()

        try:
            print("Navigating to website...")
            page.goto("https://www.soniafriedrichphotography.com/", wait_until="networkidle", timeout=30000)
            print("✓ Page loaded")

            if not HEADLESS:
                print("\n⏳ Waiting for you to click on the first sardine gallery image...")
                print("   (You have 60 seconds to find and click the gallery)")
                time.sleep(60)  # Give user time to navigate

            # Now start looking for the slideshow arrows
            print("\nLooking for gallery navigation...")
            time.sleep(2)

            # Find navigation arrows
            next_arrow_selector = '.nav-arrows-container .slideshow-arrow'

            downloaded = 0
            seen_images = set()
            max_images = 100
            consecutive_duplicates = 0
            no_image_count = 0

            for i in range(max_images):
                print(f"\n[Image {i+1}]")
                time.sleep(1.5)  # Wait for image to load

                # Find all large visible images
                all_imgs = page.query_selector_all('img[src*="wixstatic.com/media/dd09ca"]')

                current_img = None
                max_width = 0

                # Find the largest visible image (likely the gallery image)
                for img in all_imgs:
                    try:
                        if img.is_visible():
                            box = img.bounding_box()
                            if box and box['width'] > max_width:
                                max_width = box['width']
                                current_img = img
                    except:
                        continue

                if current_img and max_width > 400:  # Must be larger than 400px
                    img_src = current_img.get_attribute('src')

                    if not img_src:
                        no_image_count += 1
                        print("  No src attribute")
                        if no_image_count >= 3:
                            break
                        continue

                    original_url, ext = get_original_image_url(img_src)

                    if original_url:
                        if original_url in seen_images:
                            consecutive_duplicates += 1
                            print(f"  Already downloaded (duplicate #{consecutive_duplicates})")
                            if consecutive_duplicates >= 5:
                                print("  ✓ Reached end of gallery")
                                break
                        else:
                            consecutive_duplicates = 0
                            no_image_count = 0
                            seen_images.add(original_url)

                            img_id = re.search(r'dd09ca_([a-f0-9]+)', original_url).group(1)
                            filename = f"{OUTPUT_DIR}/sardine_{downloaded+1:03d}_{img_id}.{ext}"

                            print(f"  Image size: {max_width:.0f}px width")
                            print(f"  Downloading: ...{original_url[-60:]}")

                            if download_image_from_url(original_url, filename):
                                size_mb = os.path.getsize(filename) / 1024 / 1024
                                print(f"  ✓ Saved: {filename} ({size_mb:.2f} MB)")
                                downloaded += 1
                    else:
                        print(f"  Could not extract URL")
                else:
                    no_image_count += 1
                    print("  No large image found")
                    if no_image_count >= 3:
                        print("  No images for 3 iterations - stopping")
                        break
                    continue

                # Try to click next
                try:
                    next_arrows = page.query_selector_all(next_arrow_selector)

                    if len(next_arrows) >= 2:
                        # Second arrow is usually "next"
                        next_button = next_arrows[1]
                        if next_button.is_visible():
                            next_button.click()
                            print("  → Next")
                        else:
                            print("  Next button not visible")
                            break
                    else:
                        print(f"  Only found {len(next_arrows)} arrows")
                        break

                except Exception as e:
                    print(f"  Could not navigate: {e}")
                    break

            print(f"\n{'='*70}")
            print(f"✓ Downloaded {downloaded} unique images!")
            print(f"{'='*70}")

        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()

            try:
                page.screenshot(path="debug_screenshot.png")
                print("Debug screenshot: debug_screenshot.png")
            except:
                pass

        finally:
            if not HEADLESS:
                print("\nBrowser will close in 5 seconds...")
                time.sleep(5)
            browser.close()

    print(f"\n📁 Images saved to: {os.path.abspath(OUTPUT_DIR)}/")
    print("="*70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted")
