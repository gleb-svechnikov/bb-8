#!/bin/bash
# Launches the BB-8 + CrowPi2 control panel.
cd "$(dirname "$0")"
export SDL_VIDEO_ALLOW_SCREENSAVER=1
python3 src/main.py
