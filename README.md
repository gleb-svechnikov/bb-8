# BB-8 Control Center

A big-button keyboard-driven GUI for driving a Sphero BB-8 from the CrowPi2, built for a
kid. There's no touchscreen on this build: colors, the pentagon trick, and a live sensor
readout live on the left, each labeled with the key that triggers it, and the right side
is a green grid tracking where BB-8 has rolled.

## Controls

- **CrowPi2 joystick** — drive BB-8 around (8 directions).
- **Arrow keys / WASD** — same thing, for when you're on a laptop with no joystick.
- **1–6** — color swatches; change BB-8's main LED color (red/orange/yellow/green/blue/purple).
- **P — PENTAGON** — BB-8 rolls a 5-sided path; the CrowPi2's LED matrix does a rainbow chase.
- **R** — force a reconnect if the status dot shows red.

Below the pentagon button, the left panel shows BB-8's live sensor readings (location,
velocity, speed, heading, orientation, acceleration, gyroscope), streamed from spherov2.
The connection status dot and Bluetooth address sit at the bottom of the left column.

A mouse still works if one's plugged in (clicking the on-screen buttons), but every action
has a keyboard shortcut so the app is fully usable without a touchscreen or a mouse.

The green grid on the right plots BB-8's path as small dots as it drives, using spherov2's
dead-reckoned location relative to where it connected; a bump (BB-8's built-in collision
detection) marks a red dot on the grid where it happened.

Press `Esc` or `Q` to quit.

## Running it

```bash
./run.sh                 # windowed 1920x1000 (laptop development)
./run.sh --fullscreen    # fullscreen at native resolution (CrowPi2)
```

`run.sh` uses [uv](https://docs.astral.sh/uv/) to provision the virtualenv on first launch,
including the right Python version, so the laptop and the CrowPi2 run an identical stack.
Install uv once with `curl -LsSf https://astral.sh/uv/install.sh | sh`.

The GUI also tries to power on the host's Bluetooth adapter itself before it starts scanning.
On Linux it starts the `bluetooth` systemd service if it isn't already running (via `sudo -n`,
so it fails instantly rather than prompting for a password if that isn't set up passwordless),
then runs `rfkill unblock bluetooth` and `bluetoothctl power on`. On macOS it runs `blueutil -p 1`
if [blueutil](https://github.com/toy/blueutil) is installed (`brew install blueutil`). If none of
those tools are available, or it isn't allowed to start the service, it just skips that step
silently — turn Bluetooth on by hand in that case.

BB-8's Bluetooth name defaults to `BB-B016`. To point the app at a different toy permanently,
pass `--toy-name` once — it's saved to `~/.config/bb8-control/config.json` and reused on every
future launch, so you don't need to set anything in the shell again:

```bash
./run.sh --toy-name BB-1234
```

The `BB8_NAME` environment variable still works too, and overrides the saved config for a
single run (handy for testing with a different toy without touching the saved default):

```bash
BB8_NAME=BB-9999 ./run.sh
```

### On macOS

Nothing extra — `./run.sh` is enough. The first BLE scan will make macOS ask for Bluetooth
permission; grant it to your **terminal app** (System Settings → Privacy & Security → Bluetooth).
If you never see the prompt and connection always fails, the permission is the first thing to check.

The CrowPi2's joystick and LED matrix don't exist here, so they quietly disable
themselves and the on-screen hint switches to keyboard driving.

### On the CrowPi2

Two things are easy to get wrong, and both fail *silently* into "the LED matrix does nothing":

1. **The venv must see system site-packages.** The matrix driver `elecrow_ws281x` is not on
   PyPI — it ships preinstalled on the CrowPi2 image. `run.sh` handles this automatically on
   Linux by creating the venv with `--system-site-packages`. If you created `.venv` by hand,
   delete it and re-run `./run.sh`.
2. **The matrix needs root** for PWM/DMA:

   ```bash
   sudo -E env "PATH=$PATH" ./run.sh --fullscreen
   ```

   Without root, everything else still works; only the matrix stays dark.

**If the CrowPi2 image is 32-bit** (`uname -m` reports `armv7l`), uv may not have a managed
Python build. Point it at the system interpreter instead:

```bash
rm -rf .venv
uv venv --system-site-packages --python /usr/bin/python3
./run.sh --fullscreen
```

## Notes

- BB-8 needs to be off its charging dock and awake (give it a shake) before connecting.
- The Bluetooth stack on the CrowPi2 can be flaky — the app retries the connection
  automatically and shows a status dot (grey/yellow/green/red) up top. Press `R` to force
  a reconnect if it shows red.

### Why the dependency pins are strict

Every command to BB-8 is a **blocking BLE round-trip** of roughly 50–100 ms
(`Sphero.roll` → `Toy._execute` → `_wait_packet`). That, not Python, is the speed limit — so
the code is written to send as few packets as possible rather than to run fast locally.

`spherov2` is the only library that speaks BB-8's legacy v1 protocol, and it was last released
in January 2024 against bleak 0.x. bleak has since shipped 1.0, 2.0 and 3.0 with breaking
changes to `find_device_by_filter` and `write_gatt_char`, both of which spherov2's adapter
calls. **`bleak` is therefore pinned below 1.0** — relaxing that bound will break the
connection at runtime, not at install time. Similarly the project uses `pygame-ce` rather than
`pygame`, because upstream pygame has no wheels for current Python versions.

## Project layout

```
pyproject.toml      - pinned interpreter + dependencies (uv)
src/
  main.py           - pygame app: layout, event loop, button wiring
  bb8.py            - BB8Controller: owns the BLE connection on a background thread
  config.py         - remembers which BB-8 to connect to (~/.config/bb8-control/config.json)
  bluetooth_power.py - best-effort adapter power-on before scanning
  crowpi_io.py      - CrowPiIO: joystick, 8x8 LED matrix
  input_sources.py  - shared heading table; joystick and keyboard direction inputs
  ui.py             - Button widget, hand-drawn icons, and the movement grid
```
