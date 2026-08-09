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


# Icons all take (surface, rect, color, fill). `fill` is the button's current
# background, which icon_moon needs to punch a crescent out of the circle.
def icon_star(surface, rect, color, fill=None):
    cx, cy = rect.centerx, rect.centery - 10
    outer, inner = rect.width * 0.28, rect.width * 0.12
    points = []
    for i in range(10):
        angle = math.pi / 2 + i * math.pi / 5
        r = outer if i % 2 == 0 else inner
        points.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
    pygame.draw.polygon(surface, color, points)


def icon_speaker(surface, rect, color, fill=None):
    cx, cy = rect.centerx - 15, rect.centery - 10
    box = pygame.Rect(cx - 20, cy - 15, 20, 30)
    pygame.draw.rect(surface, color, box)
    pygame.draw.polygon(surface, color, [
        (cx, cy - 15), (cx + 25, cy - 35), (cx + 25, cy + 35), (cx, cy + 15),
    ])
    for i, r in enumerate((14, 24, 34)):
        arc_rect = pygame.Rect(cx + 20, cy - r, r * 2, r * 2)
        pygame.draw.arc(surface, color, arc_rect, -0.6, 0.6, 4)


def icon_moon(surface, rect, color, fill=None):
    cx, cy = rect.centerx, rect.centery - 10
    radius = rect.width * 0.22
    pygame.draw.circle(surface, color, (cx, cy), radius)
    # Bite a crescent out using the button's own fill. This used to sample the
    # surface at (left+2, top+2), which with border_radius=24 lands outside the
    # rounded corner and picks up the page background instead of the button.
    bite = fill if fill is not None else BLACK
    pygame.draw.circle(surface, bite, (cx + int(radius * 0.5), cy - int(radius * 0.2)), radius)


def icon_sun(surface, rect, color, fill=None):
    cx, cy = rect.centerx, rect.centery - 10
    radius = rect.width * 0.16
    pygame.draw.circle(surface, color, (cx, cy), radius)
    for i in range(8):
        angle = i * math.pi / 4
        x1 = cx + math.cos(angle) * (radius + 8)
        y1 = cy + math.sin(angle) * (radius + 8)
        x2 = cx + math.cos(angle) * (radius + 24)
        y2 = cy + math.sin(angle) * (radius + 24)
        pygame.draw.line(surface, color, (x1, y1), (x2, y2), 5)


def icon_stop(surface, rect, color, fill=None):
    cx, cy = rect.centerx, rect.centery - 10
    size = rect.width * 0.22
    pygame.draw.rect(surface, color, (cx - size / 2, cy - size / 2, size, size), border_radius=6)
