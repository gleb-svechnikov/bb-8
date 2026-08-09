"""Wraps the CrowPi2's onboard joystick, buzzer and 8x8 LED matrix.

Any hardware that fails to initialize (e.g. running this off the CrowPi2) is
disabled instead of crashing the app, so the GUI still works for testing.
"""
import threading
import time

# Analog joystick, read through the MCP3008 ADC over SPI.
X_CHANNEL = 1
Y_CHANNEL = 0
LOW_THRESHOLD = 400
HIGH_THRESHOLD = 650

BUZZER_PIN = 18
MATRIX_PIXELS = 64
MATRIX_BRIGHTNESS = 40

# heading in degrees: 0=forward/up, 90=right, 180=back/down, 270=left
DIRECTION_HEADINGS = {
    (True, False, False, False): 0,      # up
    (True, False, False, True): 45,      # up + right
    (False, False, False, True): 90,     # right
    (False, True, False, True): 135,     # down + right
    (False, True, False, False): 180,    # down
    (False, True, True, False): 225,     # down + left
    (False, False, True, False): 270,    # left
    (True, False, True, False): 315,     # up + left
}


class CrowPiIO:
    def __init__(self):
        self.joystick_available = False
        self.buzzer_available = False
        self.matrix_available = False
        self._spi = None
        self._buzzer = None
        self._matrix = None
        self._init_joystick()
        self._init_buzzer()
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

    def _init_buzzer(self):
        try:
            from gpiozero import Buzzer
            self._buzzer = Buzzer(BUZZER_PIN)
            self.buzzer_available = True
        except Exception:
            self.buzzer_available = False

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
        time.sleep(duration)

    def buzz(self, duration=0.15):
        if not self.buzzer_available:
            return
        self._buzzer.on()
        time.sleep(duration)
        self._buzzer.off()

    def play_noise_effect(self):
        """Sync'd with BB8Controller.noise(): 4 beeps + matrix flashes red/green."""
        threading.Thread(target=self._noise_effect_worker, daemon=True).start()

    def _noise_effect_worker(self):
        for _ in range(4):
            self.matrix_flash((255, 0, 0), 0.15)
            self.buzz(0.15)
            self.matrix_flash((0, 0, 0), 0.15)
        self.matrix_flash((0, 255, 0), 0.3)
        self.matrix_clear()

    def play_pentagon_effect(self):
        """Sync'd with BB8Controller.pentagon(): a rainbow chase on the matrix."""
        threading.Thread(target=self._pentagon_effect_worker, daemon=True).start()

    def _pentagon_effect_worker(self):
        if not self.matrix_available:
            return
        for j in range(256 * 3):
            r, g, b = _wheel((j) & 255)
            self._matrix.fillColor(self._Color(r, g, b))
            time.sleep(0.01)
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
