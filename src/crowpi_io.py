"""Wraps the CrowPi2's onboard joystick and 8x8 LED matrix.

Any hardware that fails to initialize (e.g. running this off the CrowPi2) is
disabled instead of crashing the app, so the GUI still works for testing.

The LED matrix driver (elecrow_ws281x) ships preinstalled on the CrowPi2 image
rather than on PyPI, and needs root for PWM/DMA -- see the README. If either is
missing the matrix simply reports itself unavailable.
"""
import threading
import time

from input_sources import DIRECTION_HEADINGS

# Analog joystick, read through the MCP3008 ADC over SPI.
X_CHANNEL = 1
Y_CHANNEL = 0
LOW_THRESHOLD = 400
HIGH_THRESHOLD = 650

MATRIX_PIXELS = 64
MATRIX_BRIGHTNESS = 40

MATRIX_FRAME_SECONDS = 0.01


class CrowPiIO:
    def __init__(self):
        self.joystick_available = False
        self.matrix_available = False
        self._spi = None
        self._matrix = None
        # Set by stop_effects() so a running light show can be cut short.
        self._abort = threading.Event()
        self._init_joystick()
        self._init_matrix()

    def _init_joystick(self):
        try:
            import spidev
            self._spi = spidev.SpiDev()
            self._spi.open(0, 1)
            self._spi.max_speed_hz = 1000000
            self.joystick_available = True
        except Exception:
            self.joystick_available = False

    def _init_matrix(self):
        try:
            from elecrow_ws281x import Color, PixelStrip
            self._Color = Color
            self._matrix = PixelStrip(MATRIX_PIXELS, MATRIX_BRIGHTNESS)
            self._matrix.begin()
            self.matrix_available = True
        except Exception:
            self.matrix_available = False

    def _read_adc(self, channel):
        resp = self._spi.xfer2([1, (8 + channel) << 4, 0])
        return ((resp[1] & 3) << 8) + resp[2]

    def read_direction(self):
        """Returns a heading in degrees, or None if the stick is centered."""
        if not self.joystick_available:
            return None
        x = self._read_adc(X_CHANNEL)
        y = self._read_adc(Y_CHANNEL)
        up = y > HIGH_THRESHOLD
        down = y < LOW_THRESHOLD
        left = x > HIGH_THRESHOLD
        right = x < LOW_THRESHOLD
        return DIRECTION_HEADINGS.get((up, down, left, right))

    def matrix_clear(self):
        if self.matrix_available:
            self._matrix.fillColor(self._Color(0, 0, 0))

    def matrix_flash(self, rgb, duration=0.2):
        if not self.matrix_available:
            return
        self._matrix.fillColor(self._Color(*rgb))
        self._wait(duration)

    def _wait(self, duration):
        """Sleep, returning False immediately if the effect was cancelled."""
        return not self._abort.wait(duration)

    def stop_effects(self):
        """Cancel any running light/sound effect (e.g. on app shutdown)."""
        self._abort.set()

    def play_pentagon_effect(self, duration):
        """Sync'd with BB8Controller.pentagon(): a rainbow chase on the matrix."""
        self._abort.clear()
        threading.Thread(target=self._pentagon_effect_worker, args=(duration,), daemon=True).start()

    def _pentagon_effect_worker(self, duration):
        if not self.matrix_available:
            return
        # Run for exactly as long as BB-8 is rolling, rather than a fixed frame
        # count that used to overrun the trick by ~2s and ignore STOP entirely.
        deadline = time.monotonic() + duration
        step = 0
        while time.monotonic() < deadline:
            r, g, b = _wheel(step & 255)
            self._matrix.fillColor(self._Color(r, g, b))
            if not self._wait(MATRIX_FRAME_SECONDS):
                break
            step += 1
        self.matrix_clear()


def _wheel(pos):
    if pos < 85:
        return pos * 3, 255 - pos * 3, 0
    elif pos < 170:
        pos -= 85
        return 255 - pos * 3, 0, pos * 3
    else:
        pos -= 170
        return 0, pos * 3, 255 - pos * 3
