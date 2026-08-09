"""Background controller that owns the BLE connection to a Sphero BB-8.

All communication with the toy happens on one dedicated thread via a command
queue, so the GUI thread never blocks on flaky BLE calls.
"""
import os
import queue
import threading
import time

from spherov2 import scanner
from spherov2.sphero_edu import SpheroEduAPI
from spherov2.types import Color

TOY_NAME = os.environ.get("BB8_NAME", "BB-B016")
CONNECT_ATTEMPTS = 10
CONNECT_RETRY_DELAY = 1.5

STATUS_DISCONNECTED = "disconnected"
STATUS_CONNECTING = "connecting"
STATUS_CONNECTED = "connected"
STATUS_ERROR = "error"

READY_COLOR = Color(0, 255, 0)
SLEEP_COLOR = Color(0, 0, 0)


class BB8Controller:
    def __init__(self, toy_name=TOY_NAME):
        self.toy_name = toy_name
        self.status = STATUS_DISCONNECTED
        self.status_detail = ""
        self.connect_attempt = 0
        self.busy = False
        self._toy = None
        self._api = None
        self._queue = queue.Queue()
        self._abort = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.connect()

    # ---- public API: called from the UI thread ----
    def connect(self):
        self._queue.put(("connect", None))

    def set_color(self, color):
        self._queue.put(("color", color))

    def drive(self, heading, speed):
        self._queue.put(("drive", (heading, speed)))

    def pentagon(self):
        self._queue.put(("pentagon", None))

    def noise(self):
        self._queue.put(("noise", None))

    def go_to_sleep(self):
        self._queue.put(("sleep", None))

    def wake_up(self):
        self._queue.put(("wake", None))

    def request_stop(self):
        self._abort.set()
        self._queue.put(("stop", None))

    # ---- worker thread ----
    def _run(self):
        while True:
            action, payload = self._queue.get()
            try:
                handler = getattr(self, f"_handle_{action}")
                handler(payload)
            except Exception as e:
                self.status, self.status_detail = STATUS_ERROR, str(e)
                self.busy = False

    def _handle_connect(self, _payload):
        self.status, self.connect_attempt = STATUS_CONNECTING, 0
        for attempt in range(1, CONNECT_ATTEMPTS + 1):
            self.connect_attempt = attempt
            try:
                toy = scanner.find_toy(toy_name=self.toy_name)
                api = SpheroEduAPI(toy)
                api.__enter__()
                self._toy, self._api = toy, api
                self._api.set_main_led(READY_COLOR)
                self.status, self.status_detail = STATUS_CONNECTED, ""
                return
            except Exception as e:
                self.status_detail = str(e) or "timed out"
                time.sleep(CONNECT_RETRY_DELAY)
        self.status = STATUS_ERROR

    def _handle_color(self, color):
        if self._api:
            self._api.set_main_led(color)

    def _handle_drive(self, payload):
        if not self._api or self.busy:
            return
        heading, speed = payload
        self._api.set_heading(heading)
        self._api.set_speed(speed)

    def _handle_stop(self, _payload):
        if self._api:
            self._api.stop_roll()

    def _handle_sleep(self, _payload):
        if not self._api:
            return
        self._api.stop_roll()
        self._api.set_main_led(SLEEP_COLOR)

    def _handle_wake(self, _payload):
        if self._api:
            self._api.set_main_led(READY_COLOR)

    def _handle_pentagon(self, _payload):
        if not self._api:
            return
        self._abort.clear()
        self.busy = True
        try:
            self._api.set_main_led(Color(0, 120, 255))
            heading = 0
            for _ in range(5):
                if self._abort.is_set():
                    break
                self._api.roll(heading, 70, 1.2)
                time.sleep(0.2)
                heading = (heading + 72) % 360
            self._api.stop_roll()
            if self.status == STATUS_CONNECTED:
                self._api.set_main_led(READY_COLOR)
        finally:
            self.busy = False

    def _handle_noise(self, _payload):
        if not self._api:
            return
        self._abort.clear()
        self.busy = True
        try:
            self._api.set_main_led(Color(255, 0, 0))
            for _ in range(4):
                if self._abort.is_set():
                    break
                self._api.spin(360, 0.3)
            if self.status == STATUS_CONNECTED:
                self._api.set_main_led(READY_COLOR)
        finally:
            self.busy = False
