#!/usr/bin/env python3
"""
Download Sardine gallery by starting from homepage and clicking into the gallery
"""

import json
import time
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright
import re

OUTPUT_DIR = Path("sharks-sardines")
OUTPUT_DIR.mkdir(exist_ok=True)
GALLERY_COMPONENT_ID = "comp-mizbkpxe"
WARMUP_SCRIPT_ID = "wix-warmup-data"

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

def parse_gallery_metadata(page):
    """Read inline warmup JSON and extract gallery metadata"""
    try:
        script_text = page.eval_on_selector(f"#{WARMUP_SCRIPT_ID}", "el => el.textContent")
        if not script_text:
            return {}
        data = json.loads(script_text)
        warmup_data = data.get("appsWarmupData", {})
        for payload in warmup_data.values():
            gallery_data = payload.get(f"{GALLERY_COMPONENT_ID}_galleryData")
            app_settings = payload.get(f"{GALLERY_COMPONENT_ID}_appSettings", {})
            if gallery_data:
                return {
                    "total": gallery_data.get("totalItemsCount"),
                    "gallery_id": app_settings.get("galleryId"),
                }
    except Exception:
        pass
    return {}

def discover_existing_images():
    """Return previously downloaded image ids and the highest sequence number"""
    id_pattern = re.compile(r"sardine_(\d+)_([a-f0-9]+)\.[a-z]+$")
    existing = {}
    highest_seq = 0
    for file_path in OUTPUT_DIR.glob("sardine_*.*"):
        match = id_pattern.match(file_path.name)
        if match:
            seq = int(match.group(1))
            img_id = match.group(2)
            highest_seq = max(highest_seq, seq)
            existing[img_id] = file_path
    return existing, highest_seq

def go_to_next_image(page):
    """Advance the gallery using arrow buttons, fallback to keyboard"""
    selectors = [
        'button[data-hook="nav-arrow-next"]',
        '#pro-gallery-pro-gallery-fullscreen-wrapper button[data-hook="nav-arrow-next"]',
        '#pro-gallery-pro-gallery-fullscreen-wrapper .slideshow-arrow:last-of-type',
        '.pro-gallery-parent-container button[class*=\"arrow\"]:last-child',
    ]

    for selector in selectors:
        arrow = None
        try:
            arrow = page.query_selector(selector)
        except Exception:
            continue

        if not arrow:
            continue

        try:
            class_attr = (arrow.get_attribute("class") or "").lower()
            aria_disabled = (arrow.get_attribute("aria-disabled") or "").lower() == "true"
            is_disabled = "disabled" in class_attr or aria_disabled
            if is_disabled:
                return False, "disabled"
            if not arrow.is_visible():
                continue
            arrow.click()
            return True, "button"
        except Exception:
            try:
                page.evaluate("(el) => el.click()", arrow)
                return True, "script"
            except Exception:
                continue

    # Keyboard fallback
    try:
        page.keyboard.press("ArrowRight")
        return True, "keyboard"
    except Exception:
        return False, "unreachable"

def main():
    print("="*70)
    print("Sardine School Gallery - Homepage Navigation Method")
    print("="*70)

    with sync_playwright() as p:
        print("\nLaunching browser...")
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})

        try:
            # Go to homepage first
            print("Loading homepage...")
            page.goto("https://www.soniafriedrichphotography.com/", wait_until="load", timeout=60000)
            time.sleep(3)
            print("✓ Homepage loaded")

            # Scroll down to find the sardine gallery section
            print("\nScrolling to find Sardine gallery...")
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            time.sleep(2)

            # Find all gallery items
            gallery_items = page.query_selector_all('[data-hook="item-wrapper"] img')
            print(f"Found {len(gallery_items)} gallery sections")

            if len(gallery_items) == 0:
                print("ERROR: No gallery items found")
                return

            # The sardine gallery should be one of these - let's click the one with the pgid in the URL
            # Or just click the first one and see
            print("\nClicking first gallery item...")
            gallery_items[0].click()
            time.sleep(3)

            # Now we should be in fullscreen gallery mode
            # Check for the Pro Gallery fullscreen wrapper
            fullscreen = page.query_selector('#pro-gallery-pro-gallery-fullscreen-wrapper')
            if fullscreen:
                print("✓ Entered fullscreen gallery mode!")
            else:
                print("WARNING: Might not be in fullscreen mode")

            existing_images, highest_sequence = discover_existing_images()
            if existing_images:
                print(f"Found {len(existing_images)} images already saved locally")

            metadata = parse_gallery_metadata(page)
            expected_total = metadata.get("total") or 50
            if metadata.get("gallery_id"):
                print(f"Gallery ID: {metadata['gallery_id']} (expects {expected_total} images)")
            else:
                print(f"Gallery metadata unavailable, defaulting to {expected_total} images")

            downloaded = 0
            session_seen_ids = set()
            consecutive_duplicates = 0

            print("\nWarming up gallery with a few navigation presses...")
            # Press next a few times to "warm up" the gallery
            for _ in range(3):
                page.keyboard.press("ArrowRight")
                time.sleep(2)  # Longer wait for initial transitions
            print("✓ Gallery warmed up, starting download...\n")

            # Download up to 50 images (safety limit)
            for i in range(50):
                print(f"\n[Image {i+1}]")

                # Wait for transitions
                time.sleep(1.5)

                # Find the CURRENT/ACTIVE gallery image
                # The gallery likely has multiple images loaded, need to find the centered/active one

                current_img = None
                img_src = None

                # Strategy 1: Find the image that's most centered in viewport
                all_gallery_imgs = page.query_selector_all('img[data-hook="gallery-item-image-img"]')

                if len(all_gallery_imgs) > 0:
                    print(f"  Found {len(all_gallery_imgs)} gallery images")

                    # Get viewport center
                    viewport_width = 1920
                    viewport_center = viewport_width / 2

                    best_img = None
                    min_distance = float('inf')

                    for img in all_gallery_imgs:
                        try:
                            if img.is_visible():
                                box = img.bounding_box()
                                if box and box['width'] > 500:
                                    # Calculate how close this image is to viewport center
                                    img_center = box['x'] + box['width'] / 2
                                    distance = abs(img_center - viewport_center)

                                    if distance < min_distance:
                                        min_distance = distance
                                        best_img = img

                        except:
                            continue

                    if best_img:
                        current_img = best_img
                        img_src = best_img.get_attribute('src')
                        print(f"  Selected centered image (offset: {min_distance:.0f}px)")

                # Strategy 2: Fallback to largest visible image
                if not current_img:
                    all_imgs = page.query_selector_all('img[src*="wixstatic.com/media/dd09ca"]')
                    max_width = 0

                    for img in all_imgs:
                        try:
                            if img.is_visible():
                                box = img.bounding_box()
                                if box and box['width'] > max_width and box['width'] > 500:
                                    max_width = box['width']
                                    current_img = img
                                    img_src = img.get_attribute('src')
                        except:
                            continue
                    if current_img:
                        print(f"  Found largest image: {max_width}px")

                if not current_img or not img_src:
                    print("  No image found")
                    break
                if not img_src:
                    print("  No src")
                    break

                # Get original URL
                original_url, ext = get_original_image_url(img_src)

                # Debug: show what we got
                if not original_url:
                    print(f"  Could not parse URL")
                    continue

                id_match = re.search(r'dd09ca_([a-f0-9]+)', original_url)
                if not id_match:
                    print("  Unable to extract image id")
                    continue

                img_id = id_match.group(1)
                print(f"  Image ID: {img_id[:12]}...")

                if img_id in session_seen_ids:
                    consecutive_duplicates += 1
                    print(f"  Already downloaded (dup #{consecutive_duplicates})")
                    if consecutive_duplicates >= 10 or len(session_seen_ids) >= expected_total:
                        print("\n  ✓ End of gallery detected (duplicates threshold)")
                        break
                else:
                    consecutive_duplicates = 0
                    session_seen_ids.add(img_id)

                    if len(session_seen_ids) >= expected_total:
                        print("  ✓ All expected images have been seen")

                    if img_id in existing_images:
                        print("  Skipping download (already on disk)")
                    else:
                        seq_number = highest_sequence + downloaded + 1
                        filename = OUTPUT_DIR / f"sardine_{seq_number:03d}_{img_id}.{ext}"

                        print(f"  Downloading...")
                        if download_image_from_url(original_url, filename):
                            size_mb = filename.stat().st_size / 1024 / 1024
                            print(f"  ✓ Saved ({size_mb:.2f} MB)")
                            downloaded += 1
                        else:
                            print("  ✗ Download failed")
                else:
                    print(f"  Could not parse URL")

                # Check if we can navigate to next image
                moved, reason = go_to_next_image(page)
                if not moved:
                    if reason == "disabled":
                        print("  ⚠ Next arrow disabled - reached last image.")
                    else:
                        print(f"  ⚠ Unable to navigate further ({reason}).")
                    break

                print(f"  → Next ({reason})")
                time.sleep(0.8)

            print(f"\n{'='*70}")
            print(f"✓ Downloaded {downloaded} unique images!")
            print(f"{'='*70}")

        except Exception as e:
            print(f"\nERROR: {e}")
            import traceback
            traceback.print_exc()

        finally:
            print("\nClosing in 3 seconds...")
            time.sleep(3)
            browser.close()

    print(f"\n📁 Images: {os.path.abspath(OUTPUT_DIR)}/")
    print("="*70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted")
