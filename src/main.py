"""BB-8 + CrowPi2 control panel for kids.

Drive BB-8 with the CrowPi2's joystick (or the arrow keys / WASD on a laptop);
tap big buttons on the touchscreen for colors and tricks. Press ESC or Q to quit.
"""
import argparse
import math
import sys

import pygame
from spherov2.types import Color

import bb8 as bb8_module
from bb8 import BB8Controller, STATUS_CONNECTED, STATUS_CONNECTING, STATUS_ERROR
from crowpi_io import CrowPiIO
from input_sources import CompositeInput, KeyboardInput
from ui import Button, icon_moon, icon_speaker, icon_star, icon_stop, icon_sun

DRIVE_SPEED = 100

# The CrowPi2's screen. Windowed mode matches it so a laptop preview shows the
# same layout the kid will actually see.
CROWPI_SIZE = (1024, 600)

COLORS = [
    ("Red", (220, 40, 40), Color(255, 0, 0)),
    ("Orange", (230, 130, 30), Color(255, 90, 0)),
    ("Yellow", (220, 200, 40), Color(255, 200, 0)),
    ("Green", (40, 180, 70), Color(0, 255, 0)),
    ("Blue", (40, 110, 220), Color(0, 100, 255)),
    ("Purple", (150, 60, 200), Color(160, 0, 220)),
]

STATUS_COLORS = {
    STATUS_CONNECTED: (40, 180, 70),
    STATUS_CONNECTING: (220, 190, 40),
    STATUS_ERROR: (210, 40, 40),
    "disconnected": (110, 110, 120),
}


def build_buttons(w, h, font):
    buttons = {}
    margin = int(w * 0.02)
    top = int(h * 0.16)

    swatch_size = int(w * 0.09)
    swatch_gap = int(w * 0.015)
    for i, (name, rgb, _color) in enumerate(COLORS):
        x = margin + i * (swatch_size + swatch_gap)
        buttons[f"color_{i}"] = Button((x, top, swatch_size, swatch_size), name, rgb, font=font)

    action_top = top + swatch_size + margin
    action_h = int(h * 0.28)
    action_w = int(w * 0.29)
    gap = int(w * 0.02)

    buttons["pentagon"] = Button(
        (margin, action_top, action_w, action_h), "PENTAGON", (60, 120, 220), icon_star, font=font
    )
    buttons["noise"] = Button(
        (margin + action_w + gap, action_top, action_w, action_h), "NOISE", (230, 140, 30), icon_speaker, font=font
    )
    buttons["sleep"] = Button(
        (margin + 2 * (action_w + gap), action_top, action_w, action_h), "SLEEP", (70, 70, 150), icon_moon, font=font
    )

    wake_w = int(w * 0.15)
    buttons["wake"] = Button(
        (margin, action_top + action_h + margin, wake_w, int(h * 0.14)), "WAKE", (240, 200, 40), icon_sun, font=font
    )

    stop_w = int(w * 0.94)
    stop_h = int(h * 0.14)
    buttons["stop"] = Button(
        (margin, h - stop_h - margin, stop_w, stop_h), "STOP", (200, 30, 30), icon_stop, font=font
    )
    return buttons


def draw_direction_indicator(surface, center, radius, heading):
    pygame.draw.circle(surface, (50, 50, 65), center, radius, width=6)
    if heading is not None:
        angle = math.radians(heading - 90)
        end = (center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle))
        pygame.draw.line(surface, (60, 200, 255), center, end, 8)
        pygame.draw.circle(surface, (60, 200, 255), (int(end[0]), int(end[1])), 14)
    else:
        pygame.draw.circle(surface, (90, 90, 100), center, 10)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="BB-8 control panel")
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="run fullscreen at native resolution (use this on the CrowPi2)",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

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
    big_font = pygame.font.SysFont(None, max(28, int(h * 0.045)), bold=True)

    bb8 = BB8Controller()
    crowpi = CrowPiIO()
    # Joystick first, keyboard as fallback -- so the same code path works on the
    # CrowPi2 and on a laptop with no CrowPi hardware attached.
    direction_input = CompositeInput(crowpi, KeyboardInput())
    buttons = build_buttons(w, h, font)
    retry_rect = pygame.Rect(int(w * 0.85) - 20, int(h * 0.02), int(w * 0.13) + 20, int(h * 0.05))

    last_heading = None

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_q):
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos
                if bb8.status == STATUS_ERROR and retry_rect.collidepoint(pos):
                    bb8.connect()
                for name, button in buttons.items():
                    if button.contains(pos):
                        button.press()
                        handle_click(name, bb8, crowpi)

        if not bb8.busy:
            heading = direction_input.read_direction()
            if heading != last_heading:
                bb8.drive(heading if heading is not None else 0, DRIVE_SPEED if heading is not None else 0)
                last_heading = heading

        for name, button in buttons.items():
            button.enabled = not bb8.busy or name == "stop"

        screen.fill((18, 18, 28))

        title = big_font.render("BB-8 CONTROL CENTER", True, (255, 255, 255))
        screen.blit(title, (int(w * 0.02), int(h * 0.02)))

        status_text = {
            STATUS_CONNECTED: "Connected!" if not bb8.busy else "Doing a trick...",
            STATUS_CONNECTING: f"Connecting... (try {bb8.connect_attempt})",
            STATUS_ERROR: "Connection lost - tap to retry",
            "disconnected": "Disconnected",
        }.get(bb8.status, bb8.status)
        dot_color = STATUS_COLORS.get(bb8.status, (110, 110, 120))
        pygame.draw.circle(screen, dot_color, (int(w * 0.85), int(h * 0.045)), 16)
        status_surf = font.render(status_text, True, (255, 255, 255))
        screen.blit(status_surf, (int(w * 0.87), int(h * 0.035)))

        if not crowpi.joystick_available:
            hint = font.render("Drive with arrow keys or WASD", True, (140, 140, 160))
            screen.blit(hint, (int(w * 0.02), int(h * 0.11)))

        for button in buttons.values():
            button.draw(screen)

        draw_direction_indicator(screen, (int(w * 0.90), int(h * 0.55)), int(w * 0.06), last_heading)

        pygame.display.flip()
        clock.tick(30)

    crowpi.stop_effects()
    bb8.shutdown()
    pygame.quit()


def handle_click(name, bb8, crowpi):
    if bb8.busy and name != "stop":
        return
    if name.startswith("color_"):
        idx = int(name.split("_")[1])
        _, _, sphero_color = COLORS[idx]
        bb8.set_color(sphero_color)
    elif name == "pentagon":
        bb8.pentagon()
        crowpi.play_pentagon_effect(bb8_module.PENTAGON_TOTAL_SECONDS)
    elif name == "noise":
        bb8.noise()
        crowpi.play_noise_effect()
    elif name == "sleep":
        bb8.go_to_sleep()
    elif name == "wake":
        bb8.wake_up()
    elif name == "stop":
        bb8.request_stop()
        crowpi.stop_effects()


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(0)
