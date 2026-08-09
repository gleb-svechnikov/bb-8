"""Direction inputs that all speak the same tiny contract.

Every source exposes ``read_direction() -> int | None``: a heading in degrees,
or None when nothing is being pressed. That lets the CrowPi2's analog joystick
and a laptop keyboard feed the exact same code path in main.py, so BB-8 can be
driven (and the driving code tested) on a MacBook that has no CrowPi hardware.
"""
import pygame

# heading in degrees: 0=forward/up, 90=right, 180=back/down, 270=left
# Keyed by (up, down, left, right). Opposing pairs (e.g. up+down) are absent on
# purpose, so a lookup miss naturally means "no direction".
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

UP_KEYS = (pygame.K_UP, pygame.K_w)
DOWN_KEYS = (pygame.K_DOWN, pygame.K_s)
LEFT_KEYS = (pygame.K_LEFT, pygame.K_a)
RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_d)


class KeyboardInput:
    """Arrow keys or WASD. The stand-in for the joystick when developing on a laptop."""

    available = True

    def read_direction(self):
        pressed = pygame.key.get_pressed()
        held = lambda keys: any(pressed[k] for k in keys)
        return DIRECTION_HEADINGS.get(
            (held(UP_KEYS), held(DOWN_KEYS), held(LEFT_KEYS), held(RIGHT_KEYS))
        )


class CompositeInput:
    """Tries each source in order and returns the first real direction.

    On the CrowPi2 the joystick wins; the keyboard stays live as a fallback if
    the joystick's SPI/ADC init failed. On a laptop only the keyboard exists.
    """

    def __init__(self, *sources):
        self.sources = [s for s in sources if getattr(s, "available", True)]

    def read_direction(self):
        for source in self.sources:
            heading = source.read_direction()
            if heading is not None:
                return heading
        return None
