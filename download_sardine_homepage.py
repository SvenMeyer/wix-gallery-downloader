#!/usr/bin/env python3
"""
Download Sardine gallery by starting from homepage and clicking into the gallery
"""

import json
import sys
import time
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright
import re

OUTPUT_DIR = Path("sharks-sardines")
OUTPUT_DIR.mkdir(exist_ok=True)
GALLERY_COMPONENT_ID = "comp-mizbkpxe"
WARMUP_SCRIPT_ID = "wix-warmup-data"
MAX_DUPLICATE_STREAK = 1

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

def focus_gallery(page):
    """Click inside the fullscreen gallery to ensure keyboard events go to it"""
    focus_selectors = [
        "#pro-gallery-pro-gallery-fullscreen-wrapper",
        ".pro-gallery-parent-container",
        "#pro-gallery-pro-gallery-fullscreen-wrapper canvas",  # rare overlay
    ]
    for selector in focus_selectors:
        try:
            element = page.query_selector(selector)
            if element and element.is_visible():
                box = element.bounding_box()
                if box:
                    x = box["x"] + box["width"] / 2
                    y = box["y"] + box["height"] / 2
                    page.mouse.click(x, y)
                    return True
        except Exception:
            continue
    return False

def get_next_arrow_state(page):
    """Return (status, element) where status is enabled/disabled/missing"""
    selectors = [
        '#pro-gallery-pro-gallery-fullscreen-wrapper button[data-hook="nav-arrow-next"]',
        '#pro-gallery-pro-gallery-fullscreen-wrapper .nav-arrows-container button:last-of-type',
        '.pro-gallery-parent-container button.slideshow-arrow:last-of-type',
        'button[data-hook="nav-arrow-next"]',
    ]

    for selector in selectors:
        try:
            arrow = page.query_selector(selector)
        except Exception:
            arrow = None

        if not arrow:
            continue

        try:
            box = arrow.bounding_box()
            visible = arrow.is_visible()
        except Exception:
            box = None
            visible = False

        if not box or box["width"] <= 0 or box["height"] <= 0 or not visible:
            continue

        try:
            arrow_eval = arrow.evaluate(
                """(el) => {
                    const style = window.getComputedStyle(el);
                    const hidden = style.display === 'none' ||
                                   style.visibility === 'hidden' ||
                                   parseFloat(style.opacity || '1') === 0 ||
                                   el.offsetParent === null;
                    const disabled = el.hasAttribute('disabled') ||
                        el.getAttribute('aria-disabled') === 'true' ||
                        style.pointerEvents === 'none';
                    return { hidden, disabled };
                }"""
            )
        except Exception:
            arrow_eval = {"hidden": False, "disabled": False}

        if arrow_eval.get("hidden"):
            continue

        inner_disabled = False
        try:
            inner_btn = arrow.query_selector("button")
            if inner_btn:
                inner_eval = inner_btn.evaluate(
                    """(el) => {
                        const style = window.getComputedStyle(el);
                        const hidden = style.display === 'none' ||
                                       style.visibility === 'hidden' ||
                                       parseFloat(style.opacity || '1') === 0 ||
                                       el.offsetParent === null;
                        const disabled = el.hasAttribute('disabled') ||
                            el.getAttribute('aria-disabled') === 'true' ||
                            style.pointerEvents === 'none';
                        return { hidden, disabled };
                    }"""
                )
                inner_disabled = inner_eval.get("disabled", False)
                if inner_eval.get("hidden"):
                    continue
        except Exception:
            pass

        if arrow_eval.get("disabled") or inner_disabled:
            return "disabled", arrow

        return "enabled", arrow

    return "missing", None

def go_to_next_image(page):
    """Advance the gallery using arrow buttons, fallback to keyboard"""
    status, arrow_ref = get_next_arrow_state(page)

    if status != "enabled" or not arrow_ref:
        return False, status

    # Try to ensure gallery captures keyboard events
    focus_gallery(page)

    try:
        page.keyboard.press("ArrowRight")
        return True, "keyboard"
    except Exception:
        pass

    # Keyboard failed, try clicking arrow explicitly
    try:
        arrow_ref.click()
        return True, "button"
    except Exception:
        try:
            page.evaluate("(el) => el.click()", arrow_ref)
            return True, "script"
        except Exception:
            return False, "unreachable"

def find_active_image(page):
    """Locate the active fullscreen image and return (element, src, strategy)"""
    active_selectors = [
        '#pro-gallery-pro-gallery-fullscreen-wrapper [data-hook="item-container"][aria-hidden="false"] img[data-hook="gallery-item-image-img"]',
        '#pro-gallery-pro-gallery-fullscreen-wrapper [data-hook="item-container"]:not([aria-hidden="true"]) img[data-hook="gallery-item-image-img"]',
    ]

    for selector in active_selectors:
        try:
            imgs = page.query_selector_all(selector)
        except Exception:
            imgs = []
        for img in imgs:
            try:
                if img.is_visible():
                    src = img.get_attribute("src") or img.get_attribute("data-src")
                    if src:
                        return img, src, "active"
            except Exception:
                continue

    return None, None, None

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
            focus_gallery(page)

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
                if len(session_seen_ids) >= expected_total:
                    print("\n  ✓ All expected images have been seen")
                    break

                print(f"\n[Image {i+1}]")
                sys.stdout.flush()

                # Wait for transitions
                time.sleep(1.5)

                # Find the CURRENT/ACTIVE gallery image
                current_img, img_src, strategy = find_active_image(page)

                if not current_img:
                    # Strategy 2: Find the image that's most centered in viewport
                    all_gallery_imgs = page.query_selector_all('img[data-hook="gallery-item-image-img"]')

                    if len(all_gallery_imgs) > 0:
                        print(f"  Found {len(all_gallery_imgs)} gallery images")

                        viewport_width = 1920
                        viewport_center = viewport_width / 2

                        best_img = None
                        min_distance = float('inf')

                        for img in all_gallery_imgs:
                            try:
                                if img.is_visible():
                                    box = img.bounding_box()
                                    if box and box['width'] > 500:
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
                            strategy = f"centered ({min_distance:.0f}px)"

                # Strategy 3: Fallback to largest visible image
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
                        strategy = f"largest ({max_width:.0f}px)"

                if not current_img or not img_src:
                    print("  No image found")
                    break
                if not img_src:
                    print("  No src")
                    break

                if strategy:
                    print(f"  Selected image via {strategy}")

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
                    if len(session_seen_ids) >= expected_total:
                        print("  ✓ All expected images have been seen")
                        break
                    status, _ = get_next_arrow_state(page)
                    if status != "enabled":
                        reason = "arrow missing" if status == "missing" else "arrow disabled"
                        print(f"  ✓ End of gallery detected ({reason})")
                        break
                    if consecutive_duplicates >= MAX_DUPLICATE_STREAK or len(session_seen_ids) >= expected_total:
                        print("\n  ✓ End of gallery detected (duplicates threshold)")
                        break
                else:
                    consecutive_duplicates = 0
                    session_seen_ids.add(img_id)

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

                    if len(session_seen_ids) >= expected_total:
                        print("  ✓ All expected images have been seen")
                        break

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

    print(f"\n📁 Images: {OUTPUT_DIR.resolve()}/")
    print("="*70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted")
