"""Small drawing helpers for big, colorful, touch-friendly buttons."""
import math
import time

import pygame

WHITE = (255, 255, 255)
BLACK = (20, 20, 30)
GREY = (90, 90, 100)

# How long a button stays visibly "pressed" after a tap. Without this a kid gets
# no feedback from a touchscreen tap and just keeps tapping.
PRESS_FEEDBACK_SECONDS = 0.12


def lighten(rgb, amount=0.35):
    return tuple(int(c + (255 - c) * amount) for c in rgb)


class Button:
    def __init__(self, rect, label, fill, icon=None, text_color=WHITE, font=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.fill = fill
        self.icon = icon
        self.text_color = text_color
        self.font = font
        self.enabled = True
        self._pressed_until = 0.0

    def contains(self, pos):
        return self.enabled and self.rect.collidepoint(pos)

    def press(self):
        self._pressed_until = time.monotonic() + PRESS_FEEDBACK_SECONDS

    def draw(self, surface):
        if not self.enabled:
            fill = GREY
        elif time.monotonic() < self._pressed_until:
            fill = lighten(self.fill)
        else:
            fill = self.fill
        pygame.draw.rect(surface, fill, self.rect, border_radius=24)
        pygame.draw.rect(surface, BLACK, self.rect, width=4, border_radius=24)
        if self.icon:
            self.icon(surface, self.rect, WHITE, fill)
        if self.label and self.font:
            text = self.font.render(self.label, True, self.text_color)
            tx = self.rect.centerx - text.get_width() // 2
            ty = self.rect.bottom - text.get_height() - 10
            surface.blit(text, (tx, ty))


# Icons all take (surface, rect, color, fill).
def icon_star(surface, rect, color, fill=None):
    cx, cy = rect.centerx, rect.centery - rect.height * 0.12
    outer, inner = min(rect.width, rect.height) * 0.28, min(rect.width, rect.height) * 0.12
    points = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        r = outer if i % 2 == 0 else inner
        points.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
    pygame.draw.polygon(surface, color, points)


GRID_BG = (8, 26, 14)
GRID_LINE = (30, 90, 45)
GRID_AXIS = (45, 140, 65)
GRID_BORDER = (60, 220, 100)
GRID_TICK = (90, 200, 120)
TRAIL_DOT = (70, 230, 110)
BUMP_DOT = (230, 60, 60)
CURRENT_DOT = (255, 255, 255)


def _dotted_line(surface, color, start, end, dash_len=4, gap_len=4):
    x1, y1 = start
    x2, y2 = end
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return
    dx, dy = (x2 - x1) / length, (y2 - y1) / length
    pos, draw = 0.0, True
    while pos < length:
        seg_end = min(pos + (dash_len if draw else gap_len), length)
        if draw:
            pygame.draw.line(surface, color, (x1 + dx * pos, y1 + dy * pos), (x1 + dx * seg_end, y1 + dy * seg_end))
        pos = seg_end
        draw = not draw


# draw_movement_grid()'s cell grid + dotted quadrant crosses are static for the
# life of the app (rect/cols/rows never change once the window is sized), but
# redrawing grid_cols*grid_rows*2 dotted lines (~8k pygame.draw.line calls at
# 28x28) every frame was a real chunk of the frame budget on the CrowPi2's Pi.
# Render it once per (size, cols, rows) and blit the cached surface instead.
_grid_lines_cache = {}


def _build_grid_lines(size, grid_cols, grid_rows):
    surf = pygame.Surface(size, pygame.SRCALPHA)
    cell_w = size[0] / grid_cols
    cell_h = size[1] / grid_rows

    for col in range(grid_cols):
        left = col * cell_w
        cx = left + cell_w / 2
        for row in range(grid_rows):
            top = row * cell_h
            _dotted_line(surf, GRID_LINE, (cx, top), (cx, top + cell_h))
    for row in range(grid_rows):
        top = row * cell_h
        cy = top + cell_h / 2
        for col in range(grid_cols):
            left = col * cell_w
            _dotted_line(surf, GRID_LINE, (left, cy), (left + cell_w, cy))

    for col in range(grid_cols + 1):
        x = col * cell_w
        pygame.draw.line(surf, GRID_LINE, (x, 0), (x, size[1]))
    for row in range(grid_rows + 1):
        y = row * cell_h
        pygame.draw.line(surf, GRID_LINE, (0, y), (size[0], y))
    return surf


def draw_movement_grid(surface, rect, trail, bumps, current_pos, heading, scale, tick_font=None,
                        grid_cols=28, grid_rows=28):
    """A green graph-paper panel: BB-8's path as small dots, bumps as red dots.

    ``trail``/``bumps`` are lists of (x, y) in cm from wherever BB-8 connected
    (spherov2's dead-reckoned origin). ``current_pos`` is the same, or None
    with no location fix yet. The panel is a fixed ``grid_cols`` x ``grid_rows``
    grid (columns ticked 1..n, rows a..z wrapping) with each cell split into
    4 quadrants by a dotted cross, when ``tick_font`` is given.
    """
    pygame.draw.rect(surface, GRID_BG, rect, border_radius=8)
    origin = rect.center

    prev_clip = surface.get_clip()
    surface.set_clip(rect)

    cell_w = rect.width / grid_cols
    cell_h = rect.height / grid_rows

    cache_key = (rect.width, rect.height, grid_cols, grid_rows)
    grid_lines = _grid_lines_cache.get(cache_key)
    if grid_lines is None:
        grid_lines = _build_grid_lines((rect.width, rect.height), grid_cols, grid_rows)
        _grid_lines_cache[cache_key] = grid_lines
    surface.blit(grid_lines, rect.topleft)

    pygame.draw.line(surface, GRID_AXIS, (rect.left, origin[1]), (rect.right, origin[1]), 2)
    pygame.draw.line(surface, GRID_AXIS, (origin[0], rect.top), (origin[0], rect.bottom), 2)

    def to_screen(pos):
        x_cm, y_cm = pos
        return int(origin[0] + x_cm * scale), int(origin[1] - y_cm * scale)

    for pos in trail:
        pygame.draw.circle(surface, TRAIL_DOT, to_screen(pos), 2)

    for pos in bumps:
        px, py = to_screen(pos)
        pygame.draw.circle(surface, BUMP_DOT, (px, py), 5)
        pygame.draw.circle(surface, WHITE, (px, py), 5, width=1)

    if current_pos is not None:
        px, py = to_screen(current_pos)
        pygame.draw.circle(surface, CURRENT_DOT, (px, py), 6)
        if heading is not None:
            angle = math.radians(heading - 90)
            end = (px + 18 * math.cos(angle), py + 18 * math.sin(angle))
            pygame.draw.line(surface, CURRENT_DOT, (px, py), end, 3)

    surface.set_clip(prev_clip)
    pygame.draw.rect(surface, GRID_BORDER, rect, width=3, border_radius=8)

    if tick_font is not None:
        for col in range(grid_cols):
            cx = rect.left + (col + 0.5) * cell_w
            label = tick_font.render(str(col + 1), True, GRID_TICK)
            surface.blit(label, (cx - label.get_width() / 2, rect.top - label.get_height() - 4))
        for row in range(grid_rows):
            cy = rect.top + (row + 0.5) * cell_h
            label = tick_font.render(chr(ord("a") + row % 26), True, GRID_TICK)
            surface.blit(label, (rect.left - label.get_width() - 4, cy - label.get_height() / 2))
