"""Background controller that owns the BLE connection to a Sphero BB-8.

All communication with the toy happens on one dedicated thread via a command
queue, so the GUI thread never blocks on flaky BLE calls.

Every command spherov2 sends is a *blocking* BLE round-trip (Sphero.roll ->
Toy._execute -> _wait_packet), costing roughly 50-100ms. That single fact drives
the design here: send as few packets as possible, never let a backlog build up,
and never block the worker thread in a way that STOP can't interrupt.

Threading note: status/status_detail/connect_attempt/busy are written here on the
worker thread and read from the UI thread without a lock. Single attribute
reads are atomic under CPython, and the UI only ever displays them, so this is
deliberate rather than an oversight -- don't "fix" it with a lock that could
deadlock against a blocking BLE call.
"""
import os
import queue
import threading

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

PENTAGON_SPEED = 70
PENTAGON_SIDE_SECONDS = 1.2
SPIN_STEP_DEGREES = 45
SPIN_STEP_SECONDS = 0.06
SPIN_REVOLUTIONS = 4

# How long each trick runs. The CrowPi2 light show is timed by hand against BB-8's
# motion, so it reads these rather than duplicating the numbers.
PENTAGON_TOTAL_SECONDS = 5 * PENTAGON_SIDE_SECONDS
NOISE_TOTAL_SECONDS = SPIN_REVOLUTIONS * (360 // SPIN_STEP_DEGREES) * SPIN_STEP_SECONDS


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
        # _abort cancels an in-flight trick (the STOP button). _shutdown is a
        # separate signal for "we're quitting" -- STOP must not kill a connection
        # attempt, but quitting must not wait out ten retries either.
        self._abort = threading.Event()
        self._shutdown = threading.Event()
        self._done = threading.Event()
        # A command pulled off the queue while coalescing drives, held for next time.
        self._pending = None
        # Last heading/speed actually transmitted, so we can skip redundant packets.
        self._sent_heading = None
        self._sent_speed = None
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

    def shutdown(self, timeout=3.0):
        """Disconnect cleanly. Blocks briefly so BLE tears down before we exit."""
        self._shutdown.set()
        self._abort.set()
        self._queue.put(("shutdown", None))
        self._done.wait(timeout)

    # ---- worker thread ----
    def _next_command(self):
        """Pull the next command, dropping drive commands that are already stale.

        A wiggling joystick can queue up drive commands faster than BLE can send
        them; without this, BB-8 replays a backlog and lags seconds behind the
        stick. Only the newest drive matters, so older ones are discarded.
        Non-drive commands are never dropped and keep their relative order.
        """
        if self._pending is not None:
            command, self._pending = self._pending, None
            return command

        action, payload = self._queue.get()
        if action != "drive":
            return action, payload

        while True:
            try:
                nxt_action, nxt_payload = self._queue.get_nowait()
            except queue.Empty:
                break
            if nxt_action == "drive":
                payload = nxt_payload  # newer input supersedes the one we were holding
            else:
                self._pending = (nxt_action, nxt_payload)
                break
        return "drive", payload

    def _run(self):
        while True:
            action, payload = self._next_command()
            if action == "shutdown":
                self._disconnect()
                return
            try:
                handler = getattr(self, f"_handle_{action}")
                handler(payload)
            except Exception as e:
                self.status, self.status_detail = STATUS_ERROR, str(e)
                self.busy = False

    def _disconnect(self):
        try:
            if self._api:
                # SpheroEduAPI is a context manager; _handle_connect entered it,
                # so this is the matching exit that actually closes the BLE link.
                self._api.__exit__(None, None, None)
        except Exception:
            pass  # nothing useful to do on the way out
        finally:
            self._api = self._toy = None
            self.status = STATUS_DISCONNECTED
            self._done.set()

    def _sleep_interruptible(self, duration):
        """Wait, returning False immediately if STOP was pressed."""
        return not self._abort.wait(duration)

    def _forget_sent_state(self):
        """Called whenever the toy's motion state changed behind our back."""
        self._sent_heading = self._sent_speed = None

    def _handle_connect(self, _payload):
        self.status, self.connect_attempt = STATUS_CONNECTING, 0
        for attempt in range(1, CONNECT_ATTEMPTS + 1):
            if self._shutdown.is_set():
                return  # quitting mid-retry; don't make the user wait it out
            self.connect_attempt = attempt
            try:
                toy = scanner.find_toy(toy_name=self.toy_name)
                api = SpheroEduAPI(toy)
                api.__enter__()
                self._toy, self._api = toy, api
                self._forget_sent_state()
                self._api.set_main_led(READY_COLOR)
                self.status, self.status_detail = STATUS_CONNECTED, ""
                return
            except Exception as e:
                self.status_detail = str(e) or "timed out"
                self._shutdown.wait(CONNECT_RETRY_DELAY)
        self.status = STATUS_ERROR

    def _handle_color(self, color):
        if self._api:
            self._api.set_main_led(color)

    def _handle_drive(self, payload):
        if not self._api or self.busy:
            return
        heading, speed = payload
        # set_heading() and set_speed() each emit a complete roll packet, and each
        # packet is a blocking round-trip. Sending both doubles the latency of every
        # direction change, so send only what actually changed. Heading goes first:
        # otherwise we'd briefly roll the *old* direction at the new speed.
        if heading != self._sent_heading:
            self._api.set_heading(heading)
            self._sent_heading = heading
        if speed != self._sent_speed:
            self._api.set_speed(speed)
            self._sent_speed = speed

    def _handle_stop(self, _payload):
        if self._api:
            self._api.stop_roll()
            self._sent_speed = 0

    def _handle_sleep(self, _payload):
        if not self._api:
            return
        self._api.stop_roll()
        self._sent_speed = 0
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
            # Roll continuously and just turn every 1.2s: one packet per side
            # instead of the roll()+stop pair, and interruptible the whole way.
            self._api.set_speed(PENTAGON_SPEED)
            heading = 0
            for _ in range(5):
                self._api.set_heading(heading)
                if not self._sleep_interruptible(PENTAGON_SIDE_SECONDS):
                    break
                heading = (heading + 72) % 360
            self._api.stop_roll()
            if self.status == STATUS_CONNECTED:
                self._api.set_main_led(READY_COLOR)
        finally:
            self._forget_sent_state()
            self.busy = False

    def _handle_noise(self, _payload):
        if not self._api:
            return
        self._abort.clear()
        self.busy = True
        try:
            self._api.set_main_led(Color(255, 0, 0))
            # Hand-rolled spin instead of spherov2's spin(): that one busy-loops a
            # blocking round-trip per step with no way to bail out, which is what
            # made STOP feel dead for seconds while NOISE was playing.
            self._api.set_speed(0)
            heading = 0
            for _ in range(SPIN_REVOLUTIONS * (360 // SPIN_STEP_DEGREES)):
                heading = (heading + SPIN_STEP_DEGREES) % 360
                self._api.set_heading(heading)
                if not self._sleep_interruptible(SPIN_STEP_SECONDS):
                    break
            if self.status == STATUS_CONNECTED:
                self._api.set_main_led(READY_COLOR)
        finally:
            self._forget_sent_state()
            self.busy = False
