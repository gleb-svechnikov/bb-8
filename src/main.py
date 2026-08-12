"""BB-8 + CrowPi2 control panel for kids.

No touchscreen on this build: colors, the pentagon trick, and a live sensor
readout are laid out on the left, triggered from the keyboard (number keys
for colors, P for pentagon). Drive with the CrowPi2's joystick (or the arrow
keys / WASD on a laptop). The right side is a green grid tracking where BB-8
has rolled, with bumps marked as small red dots. Press ESC or Q to quit.
"""
import argparse
import math
import sys

import pygame
from spherov2.types import Color

import bb8 as bb8_module
from bb8 import BB8Controller, STATUS_CONNECTED, STATUS_CONNECTING, STATUS_ERROR
from config import load_toy_name, save_toy_name
from crowpi_io import CrowPiIO
from input_sources import CompositeInput, KeyboardInput
from ui import Button, draw_movement_grid, icon_star

DRIVE_SPEED = 100

# Default windowed size for laptop development. --fullscreen (used on the CrowPi2
# itself) ignores this and renders at the display's native resolution instead.
CROWPI_SIZE = (1920, 1000)

# Width of the left (colors + tricks) panel, as a fraction of the window width.
# Shared by build_buttons() and main()'s grid_rect so the two stay in sync --
# whatever isn't spent on the left panel goes to the movement grid on the right.
LEFT_PANEL_W_FRAC = 0.40
MARGIN_FRAC = 0.02
# Where the button/grid content starts, leaving room only for the status row
# above it -- the app name lives in the window's own title bar, not on canvas.
CONTENT_TOP_FRAC = 0.09

# Pixels per centimeter on the movement grid. 1.5 puts roughly a 3m x 3m room
# on screen, which is the scale BB-8 actually rolls around in indoors.
GRID_SCALE = 1.5
# Only record a new trail point once BB-8 has moved this far, so a stationary
# (but jittery) location fix doesn't flood the trail with overlapping dots.
TRAIL_MIN_STEP_CM = 3
MAX_TRAIL_POINTS = 800
MAX_BUMP_POINTS = 150

COLORS = [
    ("Red", (220, 40, 40), Color(255, 0, 0), pygame.K_1),
    ("Orange", (230, 130, 30), Color(255, 90, 0), pygame.K_2),
    ("Yellow", (220, 200, 40), Color(255, 200, 0), pygame.K_3),
    ("Green", (40, 180, 70), Color(0, 255, 0), pygame.K_4),
    ("Blue", (40, 110, 220), Color(0, 100, 255), pygame.K_5),
    ("Purple", (150, 60, 200), Color(160, 0, 220), pygame.K_6),
]

# Deliberately clear of the WASD/arrow driving keys.
TRICK_KEYS = {
    "pentagon": (pygame.K_p, "P"),
}

STATUS_COLORS = {
    STATUS_CONNECTED: (40, 180, 70),
    STATUS_CONNECTING: (220, 190, 40),
    STATUS_ERROR: (210, 40, 40),
    "disconnected": (110, 110, 120),
}


def build_key_bindings():
    """Maps a pygame key constant to the button/command name it triggers."""
    bindings = {key: f"color_{i}" for i, (_name, _rgb, _color, key) in enumerate(COLORS)}
    for name, (key, _label) in TRICK_KEYS.items():
        bindings[key] = name
    return bindings


def build_buttons(w, h, font):
    """Lays out colors and the pentagon trick in the left half; the right half
    is the grid. Below the pentagon button, main() fills the rest of the left
    column with a live sensor readout.

    Rows are stacked with a running y cursor rather than fixed fractions of h,
    so row heights can be tuned independently without one silently drifting
    into the row above it.
    """
    buttons = {}
    margin = int(w * MARGIN_FRAC)
    left_w = int(w * LEFT_PANEL_W_FRAC)
    row_gap = int(h * 0.02)
    y = int(h * CONTENT_TOP_FRAC)

    swatch_cols = 3
    swatch_gap = int(w * 0.015)
    swatch_w = (left_w - margin - (swatch_cols - 1) * swatch_gap) // swatch_cols
    swatch_h = int(h * 0.12)
    for i, (name, rgb, _color, key) in enumerate(COLORS):
        col, row = i % swatch_cols, i // swatch_cols
        x = margin + col * (swatch_w + swatch_gap)
        row_y = y + row * (swatch_h + row_gap)
        key_label = pygame.key.name(key).upper()
        buttons[f"color_{i}"] = Button((x, row_y, swatch_w, swatch_h), f"{key_label}  {name}", rgb, font=font)
    y += 2 * swatch_h + row_gap + row_gap

    action_h = int(h * 0.14)
    buttons["pentagon"] = Button((margin, y, left_w - margin, action_h), "PENTAGON [P]", (60, 120, 220), icon_star, font=font)
    return buttons


def parse_args(argv):
    parser = argparse.ArgumentParser(description="BB-8 control panel")
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="run fullscreen at native resolution (use this on the CrowPi2)",
    )
    parser.add_argument(
        "--toy-name",
        help="BB-8's Bluetooth name to connect to (e.g. BB-1234); remembered for future runs",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.toy_name:
        save_toy_name(args.toy_name)
    toy_name = args.toy_name or load_toy_name()

    pygame.init()
    pygame.mouse.set_visible(True)
    if args.fullscreen:
        info = pygame.display.Info()
        w, h = info.current_w, info.current_h
        screen = pygame.display.set_mode((w, h), pygame.FULLSCREEN)
    else:
        w, h = CROWPI_SIZE
        screen = pygame.display.set_mode((w, h))
    pygame.display.set_caption("BB-8 Control Center")
    clock = pygame.time.Clock()

    font = pygame.font.SysFont(None, max(18, int(h * 0.022)))
    tick_font = pygame.font.SysFont(None, max(12, int(h * 0.014)))
    sensor_font = pygame.font.SysFont(None, max(16, int(h * 0.02)))

    bb8 = BB8Controller(toy_name=toy_name)
    crowpi = CrowPiIO()
    # Joystick first, keyboard as fallback -- so the same code path works on the
    # CrowPi2 and on a laptop with no CrowPi hardware attached.
    direction_input = CompositeInput(crowpi, KeyboardInput())
    buttons = build_buttons(w, h, font)
    key_bindings = build_key_bindings()

    margin = int(w * MARGIN_FRAC)
    grid_left = int(w * LEFT_PANEL_W_FRAC) + margin
    grid_top = int(h * CONTENT_TOP_FRAC)
    grid_rect = pygame.Rect(grid_left, grid_top, w - margin - grid_left, h - grid_top - margin)
    sensor_top = buttons["pentagon"].rect.bottom + int(h * 0.03)
    sensor_line_h = int(h * 0.032)
    status_y = h - margin - int(h * 0.05)

    last_heading = None
    trail = []
    bumps = []

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_ESCAPE, pygame.K_q):
                    running = False
                elif event.key == pygame.K_r and bb8.status == STATUS_ERROR:
                    # A new connection resets spherov2's locator origin to BB-8's
                    # current position, so old trail/bump points would otherwise
                    # be redrawn as if they shared the new coordinate frame.
                    trail.clear()
                    bumps.clear()
                    bb8.connect()
                elif event.key in key_bindings:
                    name = key_bindings[event.key]
                    button = buttons.get(name)
                    if button:
                        button.press()
                    handle_click(name, bb8, crowpi)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos
                for name, button in buttons.items():
                    if button.contains(pos):
                        button.press()
                        handle_click(name, bb8, crowpi)

        if not bb8.busy:
            heading = direction_input.read_direction()
            if heading != last_heading:
                bb8.drive(heading if heading is not None else 0, DRIVE_SPEED if heading is not None else 0)
                last_heading = heading

        for button in buttons.values():
            button.enabled = not bb8.busy

        current_pos = bb8.get_location()
        if current_pos is not None and (
            not trail or math.hypot(current_pos[0] - trail[-1][0], current_pos[1] - trail[-1][1]) >= TRAIL_MIN_STEP_CM
        ):
            trail.append(current_pos)
            del trail[:-MAX_TRAIL_POINTS]
        bumps.extend(bb8.poll_collisions())
        del bumps[:-MAX_BUMP_POINTS]

        screen.fill((18, 18, 28))

        status_text = {
            STATUS_CONNECTED: "Connected!" if not bb8.busy else "Doing a trick...",
            STATUS_CONNECTING: f"Connecting... (try {bb8.connect_attempt})",
            STATUS_ERROR: "Connection lost - press R to retry",
            "disconnected": "Disconnected",
        }.get(bb8.status, bb8.status)
        if bb8.address:
            status_text += f"  ({bb8.address})"
        dot_color = STATUS_COLORS.get(bb8.status, (110, 110, 120))
        pygame.draw.circle(screen, dot_color, (margin + 16, status_y + 16), 16)
        status_surf = font.render(status_text, True, (255, 255, 255))
        screen.blit(status_surf, (margin + 40, status_y + 5))

        if not crowpi.joystick_available:
            hint = font.render("Drive with arrow keys or WASD", True, (140, 140, 160))
            screen.blit(hint, (int(w * 0.02), int(h * 0.02)))

        for button in buttons.values():
            button.draw(screen)

        for i, line in enumerate(format_sensor_lines(bb8.get_sensors())):
            line_surf = sensor_font.render(line, True, (160, 190, 220))
            screen.blit(line_surf, (margin, sensor_top + i * sensor_line_h))

        draw_movement_grid(screen, grid_rect, trail, bumps, current_pos, last_heading, GRID_SCALE, tick_font)

        pygame.display.flip()
        clock.tick(30)

    crowpi.stop_effects()
    bb8.shutdown()
    pygame.quit()


def handle_click(name, bb8, crowpi):
    if bb8.busy:
        return
    if name.startswith("color_"):
        idx = int(name.split("_")[1])
        _, _, sphero_color, _key = COLORS[idx]
        bb8.set_color(sphero_color)
    elif name == "pentagon":
        bb8.pentagon()
        crowpi.play_pentagon_effect(bb8_module.PENTAGON_TOTAL_SECONDS)


def format_sensor_lines(sensors):
    """Formats a get_sensors() snapshot as "Label: value" lines for the left panel."""

    def xy(d, unit):
        return f"{d['x']:.1f}, {d['y']:.1f} {unit}" if d else "—"

    def xyz(d, unit):
        return f"{d['x']:.1f}, {d['y']:.1f}, {d['z']:.1f} {unit}" if d else "—"

    def pry(d, unit):
        return f"p{d['pitch']:.0f} r{d['roll']:.0f} y{d['yaw']:.0f} {unit}" if d else "—"

    def num(v, unit=""):
        return f"{v}{unit}" if v is not None else "—"

    return [
        f"Location: {xy(sensors['location'], 'cm')}",
        f"Velocity: {xy(sensors['velocity'], 'cm/s')}",
        f"Speed: {num(sensors['speed'])}",
        f"Heading: {num(sensors['heading'], '°')}",
        f"Orientation: {pry(sensors['orientation'], '°')}",
        f"Acceleration: {xyz(sensors['acceleration'], 'g')}",
        f"Gyroscope: {xyz(sensors['gyroscope'], '°/s')}",
    ]


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(0)
