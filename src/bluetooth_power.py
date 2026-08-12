"""Best-effort attempt to power on the host's Bluetooth adapter before scanning.

A BB-8 connection starts with a BLE scan; if the adapter is off, the scan just
fails or hangs until timeout with a confusing "connecting..." spinner and no
clue why. This tries to turn Bluetooth on first, and gives up silently when it
can't (e.g. macOS with no third-party CLI installed) rather than blocking
startup or surfacing an error the kid can't act on.
"""
import platform
import shutil
import subprocess

_TIMEOUT_SECONDS = 5


def _run(cmd):
    try:
        subprocess.run(cmd, capture_output=True, timeout=_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def ensure_bluetooth_on():
    system = platform.system()
    if system == "Linux":
        # On a fresh CrowPi2/Raspberry Pi OS boot, bluetooth.service is often not
        # running at all (not just powered off). bluetoothctl then has no bluetoothd
        # to talk to over D-Bus and hangs until our timeout instead of erroring, so
        # this has to run before bluetoothctl, not as a fallback after it. `-n`
        # keeps sudo from blocking on a password prompt if it isn't passwordless;
        # it just fails fast, which _run already swallows.
        if shutil.which("systemctl"):
            _run(["sudo", "-n", "systemctl", "start", "bluetooth"])
        # rfkill covers "soft blocked" adapters; bluetoothctl covers "powered off".
        # Harmless to run both -- unblocking an already-unblocked radio is a no-op.
        if shutil.which("rfkill"):
            _run(["rfkill", "unblock", "bluetooth"])
        if shutil.which("bluetoothctl"):
            _run(["bluetoothctl", "power", "on"])
    elif system == "Darwin":
        # macOS has no built-in CLI for this; blueutil (brew install blueutil) is
        # the common workaround. Without it, we leave Bluetooth alone.
        if shutil.which("blueutil"):
            _run(["blueutil", "-p", "1"])
