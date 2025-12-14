#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python3 download_sardine_interactive.py
