# BB-8 Control Center

A big-button touchscreen GUI for driving a Sphero BB-8 from the CrowPi2, built for a kid.

## Controls

- **CrowPi2 joystick** — drive BB-8 around (8 directions).
- **Color swatches** — change BB-8's main LED color.
- **PENTAGON** — BB-8 rolls a 5-sided path; the CrowPi2's LED matrix does a rainbow chase.
- **NOISE** — BB-8 spins in place (no speaker on this BB-8 model, so it "buzzes" instead);
  the CrowPi2 buzzer beeps and its LED matrix flashes in sync.
- **SLEEP / WAKE** — turns BB-8's light off/on.
- **STOP** — cancels whatever BB-8 is doing right now.

Press `Esc` or `Q` to quit.

## Running it

```bash
./run.sh
```

BB-8's Bluetooth name is read from the `BB8_NAME` environment variable, defaulting to `BB-B016`:

```bash
BB8_NAME=BB-1234 ./run.sh
```

## Notes

- BB-8 needs to be off its charging dock and awake (give it a shake) before connecting.
- The Bluetooth stack on the CrowPi2 can be flaky — the app retries the connection
  automatically and shows a status dot (grey/yellow/green/red) up top. Tap the status
  area to force a reconnect if it shows red.
- If run somewhere without the CrowPi2's joystick/buzzer/LED matrix hardware, those
  features quietly disable themselves instead of crashing.

## Project layout

```
src/
  main.py      - pygame app: layout, event loop, button wiring
  bb8.py       - BB8Controller: owns the BLE connection on a background thread
  crowpi_io.py - CrowPiIO: joystick, buzzer, 8x8 LED matrix
  ui.py        - Button widget and hand-drawn icons
```
