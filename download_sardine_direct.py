#!/usr/bin/env python3
"""
Direct download script for Sardine School gallery
Goes directly to the gallery URL and clicks through all images
"""

import os
import time
import requests
from playwright.sync_api import sync_playwright
import re

OUTPUT_DIR = "sardine_school_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Direct URL to the sardine gallery
GALLERY_URL = "https://www.soniafriedrichphotography.com/?pgid=mizbkpxe-07b7c362-d9d3-4778-a29b-1a5f3e355a1c"

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
        print(f"    Error: {e}")
        return False

def get_original_image_url(img_src):
    """Extract the original quality image URL"""
    match = re.search(r'(https://static\.wixstatic\.com/media/dd09ca_[a-f0-9]+~mv2\.(jpg|jpeg|png))', img_src)
    if match:
        return match.group(1), match.group(2)
    return None, None

def main():
    print("="*70)
    print("Sardine School Gallery - Direct Downloader")
    print("="*70)
    print(f"\nGallery URL: {GALLERY_URL}")

    with sync_playwright() as p:
        print("\nLaunching browser...")
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})

        try:
            print("Navigating directly to gallery...")
            # Use "load" instead of "networkidle" - Wix sites have continuous network activity
            page.goto(GALLERY_URL, wait_until="load", timeout=60000)
            print("✓ Gallery loaded")

            # Wait for gallery to fully render
            print("Waiting for gallery to render...")
            time.sleep(5)

            # Find the pro gallery container
            print("\nLooking for Pro Gallery container...")
            gallery_container = page.query_selector('#pro-gallery-pro-gallery-fullscreen-wrapper')

            if not gallery_container:
                print("ERROR: Gallery container not found!")
                page.screenshot(path="debug.png")
                return

            print("✓ Found Pro Gallery container")

            # Look for navigation arrows within the gallery
            print("Looking for navigation arrows...")

            # Try multiple arrow selectors
            arrow_selectors = [
                '#pro-gallery-pro-gallery-fullscreen-wrapper .slideshow-arrow',
                '#pro-gallery-pro-gallery-fullscreen-wrapper button[aria-label*="next"]',
                '.pro-gallery-parent-container .slideshow-arrow',
                '.nav-arrows-container .slideshow-arrow',
                'button.slideshow-arrow'
            ]

            arrows = []
            next_arrow_selector = None

            for sel in arrow_selectors:
                arrows = page.query_selector_all(sel)
                if len(arrows) >= 1:
                    print(f"✓ Found {len(arrows)} arrows using: {sel}")
                    next_arrow_selector = sel
                    break

            # Fallback: use keyboard navigation
            use_keyboard = len(arrows) == 0
            if use_keyboard:
                print("⚠ No arrow buttons found - will use keyboard navigation (ArrowRight)")
            else:
                print(f"Will use button navigation ({len(arrows)} arrows found)")

            downloaded = 0
            seen_images = set()
            consecutive_duplicates = 0

            # Download up to 50 images
            for i in range(50):
                print(f"\n[Image {i+1}]")
                time.sleep(1.5)  # Wait for image to load

                # Find the current image
                # Try multiple selectors
                current_img = None

                # Method 1: Find the largest visible image
                all_imgs = page.query_selector_all('img[src*="wixstatic.com/media/dd09ca"]')
                max_width = 0

                for img in all_imgs:
                    try:
                        if img.is_visible():
                            box = img.bounding_box()
                            if box and box['width'] > max_width and box['width'] > 500:
                                max_width = box['width']
                                current_img = img
                    except:
                        continue

                if not current_img:
                    print("  No large image found")
                    break

                img_src = current_img.get_attribute('src')
                if not img_src:
                    print("  No src attribute")
                    break

                # Get original quality URL
                original_url, ext = get_original_image_url(img_src)

                if original_url:
                    # Check for duplicates
                    if original_url in seen_images:
                        consecutive_duplicates += 1
                        print(f"  Duplicate #{consecutive_duplicates}")
                        if consecutive_duplicates >= 3:
                            print("\n  ✓ End of gallery detected (3 duplicates)")
                            break
                    else:
                        consecutive_duplicates = 0
                        seen_images.add(original_url)

                        img_id = re.search(r'dd09ca_([a-f0-9]+)', original_url).group(1)
                        filename = f"{OUTPUT_DIR}/sardine_{downloaded+1:03d}_{img_id}.{ext}"

                        print(f"  Image: {max_width:.0f}px wide")
                        print(f"  Downloading...")

                        if download_image_from_url(original_url, filename):
                            size_mb = os.path.getsize(filename) / 1024 / 1024
                            print(f"  ✓ Saved: {filename} ({size_mb:.2f} MB)")
                            downloaded += 1
                else:
                    print(f"  Could not parse URL: {img_src[:80]}")

                # Navigate to next image
                try:
                    if use_keyboard:
                        # Use keyboard navigation
                        page.keyboard.press("ArrowRight")
                        print("  → Next (keyboard)")
                    else:
                        # Use button click
                        arrows = page.query_selector_all(next_arrow_selector)
                        if len(arrows) >= 2:
                            next_btn = arrows[1]  # Second arrow is usually "next"
                        elif len(arrows) == 1:
                            next_btn = arrows[0]
                        else:
                            print("  Arrows disappeared - trying keyboard")
                            page.keyboard.press("ArrowRight")
                            print("  → Next (keyboard fallback)")
                            continue

                        # Try JavaScript click first (most reliable)
                        try:
                            page.evaluate('(btn) => btn.click()', next_btn)
                            print("  → Next (button)")
                        except:
                            # Fallback to keyboard
                            print("  Button click failed, using keyboard")
                            page.keyboard.press("ArrowRight")
                            print("  → Next (keyboard)")

                except Exception as e:
                    print(f"  Navigation error: {e}")
                    # Last resort - try keyboard
                    try:
                        page.keyboard.press("ArrowRight")
                        print("  → Next (keyboard emergency fallback)")
                    except:
                        print("  All navigation methods failed - stopping")
                        break

            print(f"\n{'='*70}")
            print(f"✓ Downloaded {downloaded} unique images!")
            print(f"{'='*70}")

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()

            try:
                page.screenshot(path="error_screenshot.png")
                print("Error screenshot: error_screenshot.png")
            except:
                pass

        finally:
            print("\nClosing browser in 3 seconds...")
            time.sleep(3)
            browser.close()

    print(f"\n📁 Images saved to: {os.path.abspath(OUTPUT_DIR)}/")
    print("="*70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted")
