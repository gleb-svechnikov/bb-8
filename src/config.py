"""Where BB-8's Bluetooth name is remembered across runs.

Precedence: --toy-name CLI flag > BB8_NAME env var (one-off override) >
saved config file > default. The CLI flag also writes the config file, so
picking a BB-8 once is remembered on future launches without exporting an
env var every session.
"""
import json
import os
from pathlib import Path

DEFAULT_TOY_NAME = "BB-B016"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "bb8-control"
CONFIG_PATH = CONFIG_DIR / "config.json"


def load_toy_name():
    env_name = os.environ.get("BB8_NAME")
    if env_name:
        return env_name
    try:
        data = json.loads(CONFIG_PATH.read_text())
        name = data.get("toy_name")
        if name:
            return name
    except (OSError, ValueError):
        pass
    return DEFAULT_TOY_NAME


def save_toy_name(name):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"toy_name": name}))
