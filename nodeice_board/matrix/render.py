"""
Rendering primitives for the matrix display.

Everything here is deliberately independent of the concrete matrix
backend: functions take the backend's ``graphics`` module (or a test
fake) as a parameter, so the visual logic is unit-testable without
hardware.
"""

import math
from typing import Tuple

# -- Palette ------------------------------------------------------------------
#
# A restrained palette reads far better on an LED matrix than saturated
# RGB primaries: Meshtastic green for identity, soft white for content,
# amber for accents/IDs, and dimmed variants for supporting text.

MESH_GREEN = (103, 234, 148)   # Meshtastic brand green
TEAL = (64, 200, 220)          # Accent-line companion hue
AMBER = (255, 170, 40)         # Post IDs / attention
SOFT_WHITE = (225, 232, 228)   # Body text
DIM_GREY = (95, 105, 100)      # Labels, de-emphasised text
NIGHT_GREEN = (26, 60, 40)     # Background twinkles


def scale(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    """Scale a color's brightness by factor (clamped to 0..1)."""
    factor = max(0.0, min(1.0, factor))
    return tuple(int(c * factor) for c in color)


def lerp(a: Tuple[int, int, int], b: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    """Linearly interpolate between two colors, t in 0..1."""
    t = max(0.0, min(1.0, t))
    return tuple(int(ca + (cb - ca) * t) for ca, cb in zip(a, b))


def pulse(t: float, period: float = 2.0, low: float = 0.35, high: float = 1.0) -> float:
    """A smooth sinusoidal brightness pulse between low and high."""
    phase = (math.sin(2 * math.pi * t / period) + 1) / 2
    return low + (high - low) * phase


# -- Text helpers -------------------------------------------------------------

def text_width(font, text: str) -> int:
    """Pixel width of text in the given BDF font."""
    return sum(font.CharacterWidth(ord(ch)) for ch in text)


def draw_text(gfx, canvas, font, x: int, baseline_y: int,
              color: Tuple[int, int, int], text: str) -> int:
    """Draw text and return its pixel width."""
    return gfx.DrawText(canvas, font, x, baseline_y, gfx.Color(*color), text)


def draw_text_centered(gfx, canvas, font, baseline_y: int,
                       color: Tuple[int, int, int], text: str, width: int) -> None:
    """Draw text horizontally centered on a canvas of the given width."""
    x = (width - text_width(font, text)) // 2
    draw_text(gfx, canvas, font, x, baseline_y, color, text)


# -- Animated widgets ----------------------------------------------------------

class Marquee:
    """
    A continuously looping horizontal scroller.

    The text wraps seamlessly: it is drawn twice with a fixed gap, so the
    loop has no visible jump. Text can be swapped at any time without
    resetting the scroll position, which keeps the motion calm when the
    stats it displays are refreshed.
    """

    def __init__(self, font, width: int, speed_px_s: float = 13.0, gap_px: int = 14):
        self.font = font
        self.width = width
        self.speed = speed_px_s
        self.gap = gap_px
        self.text = ""
        self._text_px = 0
        self.offset = 0.0

    def set_text(self, text: str):
        if text != self.text:
            self.text = text
            self._text_px = text_width(self.font, text)

    def step(self, dt: float):
        if self._text_px <= 0:
            return
        self.offset = (self.offset + self.speed * dt) % (self._text_px + self.gap)

    def draw(self, gfx, canvas, baseline_y: int, color: Tuple[int, int, int]):
        if not self.text:
            return
        span = self._text_px + self.gap
        x = -int(self.offset)
        # Draw enough copies to cover the panel regardless of text length
        while x < self.width:
            draw_text(gfx, canvas, self.font, x, baseline_y, color, self.text)
            x += span


class ScrollLine:
    """
    A one-shot scroller: text enters from the right and exits left.

    Supports an optional colored prefix (e.g. an amber "#42 ") that moves
    together with the body text. `done` becomes True after `passes`
    complete traversals.
    """

    def __init__(self, font, width: int, body: str, prefix: str = "",
                 speed_px_s: float = 26.0, passes: int = 1):
        self.font = font
        self.width = width
        self.body = body
        self.prefix = prefix
        self.speed = speed_px_s
        self.passes = passes
        self.completed = 0
        self._prefix_px = text_width(font, prefix) if prefix else 0
        self._total_px = self._prefix_px + text_width(font, body)
        self.x = float(width)

    @property
    def done(self) -> bool:
        return self.completed >= self.passes

    def step(self, dt: float):
        if self.done:
            return
        self.x -= self.speed * dt
        if self.x < -self._total_px:
            self.completed += 1
            if not self.done:
                self.x = float(self.width)

    def draw(self, gfx, canvas, baseline_y: int,
             body_color: Tuple[int, int, int],
             prefix_color: Tuple[int, int, int] = AMBER):
        if self.done:
            return
        x = int(self.x)
        if self.prefix:
            draw_text(gfx, canvas, self.font, x, baseline_y, prefix_color, self.prefix)
        draw_text(gfx, canvas, self.font, x + self._prefix_px, baseline_y, body_color, self.body)


def draw_accent_line(gfx, canvas, y: int, width: int, t: float):
    """
    The signature accent: a 1px line whose hue drifts slowly between
    Meshtastic green and teal in a gentle travelling wave.
    """
    for x in range(width):
        wave = (math.sin(2 * math.pi * (x / width) - t * 0.9) + 1) / 2
        color = lerp(MESH_GREEN, TEAL, wave)
        # Keep it understated so it frames the content instead of shouting
        canvas.SetPixel(x, y, *scale(color, 0.55))


def draw_ring(canvas, cx: float, cy: float, radius: float,
              color: Tuple[int, int, int], width: int, height: int):
    """Draw a 1px circle outline with SetPixel (clipped to the canvas)."""
    if radius <= 0:
        return
    steps = max(16, int(radius * 10))
    for i in range(steps):
        angle = 2 * math.pi * i / steps
        x = int(round(cx + radius * math.cos(angle)))
        y = int(round(cy + radius * math.sin(angle)))
        if 0 <= x < width and 0 <= y < height:
            canvas.SetPixel(x, y, *color)


def ellipsize(text: str, max_chars: int) -> str:
    """Trim long content so a scroll pass stays a sensible length."""
    text = " ".join(text.split())  # Collapse newlines/whitespace runs
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 1].rstrip() + "…"
