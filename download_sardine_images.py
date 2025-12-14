#!/usr/bin/env python3
"""
Script to download images from Sonia Friedrich Photography website
specifically for the "Sardine School Survival" gallery (Dec 2025)

Since the gallery is loaded dynamically with JavaScript, this script:
1. Downloads the page HTML
2. Extracts ALL full-size image URLs
3. Filters to keep only large gallery images (skips thumbnails/icons)
4. Downloads the original quality versions

Note: This will download all images on the homepage. The sardine gallery
images should be among them.
"""

import requests
import re
import os
import time

# Configuration
BASE_URL = "https://www.soniafriedrichphotography.com/"
OUTPUT_DIR = "sardine_school_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_page_html():
    """Fetch the homepage HTML"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    print(f"Fetching {BASE_URL}...")
    response = requests.get(BASE_URL, headers=headers)
    response.raise_for_status()
    return response.text

def extract_all_image_urls(html):
    """Extract all Wix image URLs from the HTML"""
    # Pattern for complete Wix image URLs
    pattern = r'(https://static\.wixstatic\.com/media/dd09ca_[a-f0-9]+~mv2\.(jpg|jpeg|png)[^"\s\'<>]*)'
    matches = re.findall(pattern, html)

    urls = set()
    for url, ext in matches:
        # Clean up the URL (remove anything after spaces or quotes)
        clean_url = url.split()[0]
        urls.add(clean_url)

    return list(urls)

def get_image_id_and_ext(url):
    """Extract image ID and extension from URL"""
    match = re.search(r'dd09ca_([a-f0-9]+)~mv2\.(jpg|jpeg|png)', url)
    if match:
        return match.group(1), match.group(2)
    return None, None

def get_original_url(image_id, ext):
    """Get the original, full-quality image URL"""
    return f"https://static.wixstatic.com/media/dd09ca_{image_id}~mv2.{ext}"

def is_large_image(url):
    """
    Check if this is likely a full-size gallery image (not a thumbnail).
    Large images typically have width >= 800px in their URL parameters.
    """
    # Look for width parameter
    width_match = re.search(r'[/,]w_(\d+)', url)
    if width_match:
        width = int(width_match.group(1))
        # Consider images with width >= 800px as gallery images
        return width >= 800

    # If no width parameter, check for quality indicators
    # fit/ URLs are usually full-size, fill/ can be various sizes
    if '/fit/' in url or '/fill/w_1' in url:
        return True

    return False

def filter_gallery_images(urls):
    """Filter URLs to keep only full-size gallery images"""
    # Get unique image IDs with their largest versions
    image_info = {}

    for url in urls:
        img_id, ext = get_image_id_and_ext(url)
        if not img_id:
            continue

        # Skip very small images (likely icons/logos)
        if any(x in url.lower() for x in ['blur_2', 'w_24,', 'w_42,', 'w_63,', 'w_79,']):
            continue

        # Skip known non-gallery images
        if any(x in img_id for x in ['4d90091e']):  # Logo/icon IDs
            continue

        # Check if it's a large image
        if is_large_image(url):
            if img_id not in image_info:
                image_info[img_id] = (img_id, ext)

    return list(image_info.values())

def download_image(url, image_id, ext, index, session):
    """Download a single image"""
    try:
        print(f"\n[{index}] Image ID: {image_id}")
        print(f"    Downloading...")

        response = session.get(url, timeout=30, stream=True)
        response.raise_for_status()

        filename = f"{OUTPUT_DIR}/image_{index:03d}_{image_id}.{ext}"

        # Download with progress
        downloaded = 0
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

        size_mb = downloaded / 1024 / 1024
        print(f"    ✓ Saved: {filename}")
        print(f"    Size: {size_mb:.2f} MB")
        return True

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"    ✗ Not found (404)")
        else:
            print(f"    ✗ HTTP Error {e.response.status_code}")
        return False
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False

def main():
    print("="*70)
    print("Sonia Friedrich Photography - Image Downloader")
    print("Targeting: Sardine School Survival Gallery (Dec 2025)")
    print("="*70)

    # Fetch HTML
    html = get_page_html()
    print(f"✓ Page fetched ({len(html) / 1024:.1f} KB)")

    # Extract all image URLs
    print("\nExtracting image URLs...")
    all_urls = extract_all_image_urls(html)
    print(f"✓ Found {len(all_urls)} total image references")

    # Filter to gallery images only
    print("\nFiltering for gallery-sized images...")
    gallery_images = filter_gallery_images(all_urls)

    if not gallery_images:
        print("\n✗ No gallery images found!")
        print("This might mean:")
        print("  - The gallery is loaded entirely via JavaScript")
        print("  - The filtering criteria need adjustment")
        return

    print(f"✓ Found {len(gallery_images)} gallery images")

    # Create download session
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': BASE_URL
    })

    # Download images
    print(f"\nDownloading {len(gallery_images)} images...")
    print("-"*70)

    successful = 0
    failed = 0

    for i, (img_id, ext) in enumerate(gallery_images, 1):
        url = get_original_url(img_id, ext)

        if download_image(url, img_id, ext, i, session):
            successful += 1
        else:
            failed += 1

        # Be respectful to the server
        if i < len(gallery_images):
            time.sleep(1)

    # Summary
    print("\n" + "="*70)
    print("Download Complete!")
    print("="*70)
    print(f"✓ Successful: {successful}")
    if failed > 0:
        print(f"✗ Failed: {failed}")
    print(f"\n📁 Images saved to: {os.path.abspath(OUTPUT_DIR)}/")
    print("\nNote: This downloaded all gallery images from the homepage.")
    print("The Sardine School gallery images should be among them.")
    print("="*70)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nDownload interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
