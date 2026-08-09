#!/bin/bash
# Launches the BB-8 + CrowPi2 control panel.
#
#   ./run.sh                 windowed 1024x600 (laptop development)
#   ./run.sh --fullscreen    fullscreen at native resolution (CrowPi2)
#
# Dependencies are provisioned by uv on first launch, including the correct
# Python version, so the Mac and the CrowPi2 run an identical stack.
set -euo pipefail
cd "$(dirname "$0")"

export SDL_VIDEO_ALLOW_SCREENSAVER=1

if [ ! -d .venv ]; then
    if [ "$(uname -s)" = "Linux" ]; then
        # The CrowPi2's LED matrix driver (elecrow_ws281x) is preinstalled system-wide
        # and is not on PyPI, so the venv must be able to see system site-packages.
        uv venv --system-site-packages
    else
        uv venv
    fi
fi

uv sync
exec uv run --no-sync python src/main.py "$@"
