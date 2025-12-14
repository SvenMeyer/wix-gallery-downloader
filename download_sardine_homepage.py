#!/usr/bin/env python3
"""
Download Sardine gallery by starting from homepage and clicking into the gallery
"""

import os
import time
import requests
from playwright.sync_api import sync_playwright
import re

OUTPUT_DIR = "sharks-sardines"
os.makedirs(OUTPUT_DIR, exist_ok=True)

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

            downloaded = 0
            seen_images = set()
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
                if original_url:
                    img_id = re.search(r'dd09ca_([a-f0-9]+)', original_url).group(1)
                    print(f"  Image ID: {img_id[:12]}...")

                if original_url:
                    if original_url in seen_images:
                        consecutive_duplicates += 1
                        print(f"  Already downloaded (dup #{consecutive_duplicates})")
                        # High threshold - gallery might take time to loop or arrow might not disable
                        if consecutive_duplicates >= 10:
                            print("\n  ✓ End of gallery detected (10 consecutive duplicates)")
                            break
                    else:
                        consecutive_duplicates = 0
                        seen_images.add(original_url)

                        img_id = re.search(r'dd09ca_([a-f0-9]+)', original_url).group(1)
                        filename = f"{OUTPUT_DIR}/sardine_{downloaded+1:03d}_{img_id}.{ext}"

                        print(f"  Downloading...")
                        if download_image_from_url(original_url, filename):
                            size_mb = os.path.getsize(filename) / 1024 / 1024
                            print(f"  ✓ Saved ({size_mb:.2f} MB)")
                            downloaded += 1
                else:
                    print(f"  Could not parse URL")

                # Check if we can navigate to next image
                # Look for the next arrow button to see if we're on the last image
                next_arrow_selectors = [
                    'button.slideshow-arrow:last-of-type',
                    '.slideshow-arrow:nth-of-type(2)',
                    '.pro-gallery-parent-container button[class*="arrow"]:last-child',
                ]

                next_arrow = None
                for selector in next_arrow_selectors:
                    try:
                        arrows = page.query_selector_all(selector)
                        if len(arrows) > 0:
                            next_arrow = arrows[-1] if len(arrows) > 1 else arrows[0]
                            if next_arrow:
                                break
                    except:
                        continue

                # Check if next arrow is disabled/hidden (indicates last image)
                can_go_next = True  # Default to true
                if next_arrow:
                    try:
                        is_visible = next_arrow.is_visible()
                        # Also check for disabled class or opacity
                        class_name = next_arrow.get_attribute('class') or ''
                        is_disabled = 'disabled' in class_name.lower()

                        can_go_next = is_visible and not is_disabled

                        if not can_go_next:
                            print(f"  ⚠ Next arrow is disabled - this is the LAST image!")
                            print(f"\n  ✓ Reached end of gallery (arrow disabled)")
                            break
                    except Exception as e:
                        # If we can't check, assume we can continue
                        pass

                # Navigate using keyboard
                page.keyboard.press("ArrowRight")
                print("  → Next")

                # Wait for transition
                time.sleep(0.5)

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
