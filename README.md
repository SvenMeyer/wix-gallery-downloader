# Sardine School (Wix) Gallery Downloader

Automates Chromium with Playwright to open the Sonia Friedrich homepage, enter the Sardine School Pro Gallery, navigate every slide, and download the original-resolution images (`dd09ca_*~mv2` on static.wixstatic.com) into `sharks-sardines/`. It now picks up all 37 images and stops as soon as the gallery signals “no more slides.”

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install playwright requests
python3 -m playwright install chromium
```

## Run

```bash
./run_homepage.sh
```

This launches a visible Chromium window, scrolls to the sardine gallery, clicks into fullscreen, drives `ArrowRight`, detects the active slide, and saves any unseen originals to `sharks-sardines/`.

## What Works
- Grabs all 37 sardine images in original quality (~3–4 MB each).
- Skips files already present on disk; reruns are fast and idempotent.
- Stops immediately when the gallery’s “next” arrow disappears/turns off (no long duplicate loops).
- Uses the inline Wix warmup JSON to know the expected image count.

## Quirks & Lessons Learned
- Wix clones multiple `<img>` nodes; we must target the active fullscreen container (`aria-hidden="false"`) to get the real slide.
- Keyboard navigation is the most reliable trigger; the script clicks the gallery first to ensure focus.
- The DOM can report dozens of `<img>` elements; counting them is misleading. Rely on CDN hashes + warmup metadata instead.
- Console output may appear slightly buffered because Playwright flushes around navigation; images still save in real time.

## Known Limitations
- Designed for this specific gallery structure; selectors may need adjustment on different Wix themes.
- Requires a visible browser (headless is brittle with this widget).
- No parallel downloads; it walks the slideshow sequentially.

## Future Improvements
1) Generalize selectors and warmup parsing to handle other Wix Pro Gallery pages.  
2) Optional headless mode with explicit waits in case UX changes.  
3) Add a “direct URL list” mode that skips the browser if warmup JSON yields all media URIs.
