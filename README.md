# Wix Gallery Downloader

Download all images from Wix Pro Gallery slideshows, bypassing browser download restrictions.

## Current Status
Work in progress - downloads 34 of 37 images from the target gallery.

## Quick Start

```bash
# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install playwright requests
python3 -m playwright install chromium

# Run
./run_homepage.sh
```

## How It Works

1. Opens browser and navigates to gallery homepage
2. Clicks into the first gallery to enter fullscreen mode
3. Uses keyboard navigation (ArrowRight) to cycle through images
4. Detects the centered/active image in viewport
5. Downloads original quality version (bypassing Wix transformations)

## Output

Images saved to `sharks-sardines/` directory with original quality (~3-4 MB each).

## Known Issues

- Currently downloads 34/37 images
- First few images may be skipped due to slow initial transitions
- Stops when detecting duplicate images (gallery loops back)

## TODO

- Fix detection of last 3 images
- Improve duplicate detection
- Add arrow button detection for end-of-gallery
