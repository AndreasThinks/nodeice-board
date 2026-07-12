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


GAMMA = 2.2


def fade(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    """
    Scale a color's brightness perceptually, for animated fades.

    LED output is roughly linear in drive level but the eye is not: a
    linearly-scaled fade appears to hang near full brightness and then
    snap off. Running the factor through a gamma curve makes pulses,
    crossfades and ring trails read as smooth, continuous motion. Use
    plain `scale` for hand-tuned static dim levels.
    """
    factor = max(0.0, min(1.0, factor))
    return scale(color, factor ** GAMMA)


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

    The line is a sequence of (text, color) segments so key tokens (the
    !post / !help commands) can be highlighted; a segment color of None
    uses the default color passed to draw().
    """

    def __init__(self, font, width: int, speed_px_s: float = 13.0, gap_px: int = 14):
        self.font = font
        self.width = width
        self.speed = speed_px_s
        self.gap = gap_px
        self.text = ""
        self.segments = []
        self._seg_px = []
        self._text_px = 0
        self.offset = 0.0

    def set_text(self, text: str):
        self.set_segments([(text, None)])

    def set_segments(self, segments):
        segments = [(text, color) for text, color in segments if text]
        if segments == self.segments:
            return
        self.segments = segments
        self.text = "".join(text for text, _ in segments)
        self._seg_px = [text_width(self.font, text) for text, _ in segments]
        self._text_px = sum(self._seg_px)

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
            seg_x = x
            for (text, seg_color), seg_px in zip(self.segments, self._seg_px):
                draw_text(gfx, canvas, self.font, seg_x, baseline_y,
                          seg_color or color, text)
                seg_x += seg_px
            x += span


class ScrollLine:
    """
    A one-shot scroller: text enters from the right and exits left.

    The line is a sequence of (text, color) segments drawn back to back,
    so e.g. an amber "#42 " id, white content and green author name move
    together as one line. `done` becomes True after `passes` complete
    traversals.
    """

    def __init__(self, font, width: int, segments,
                 speed_px_s: float = 26.0, passes: int = 1):
        self.font = font
        self.width = width
        self.segments = [(text, color) for text, color in segments if text]
        self.speed = speed_px_s
        self.passes = passes
        self.completed = 0
        self._seg_px = [text_width(font, text) for text, _ in self.segments]
        self._total_px = sum(self._seg_px)
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

    def draw(self, gfx, canvas, baseline_y: int):
        if self.done:
            return
        x = int(self.x)
        for (text, color), seg_px in zip(self.segments, self._seg_px):
            draw_text(gfx, canvas, self.font, x, baseline_y, color, text)
            x += seg_px


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


def draw_line(canvas, x0: float, y0: float, x1: float, y1: float,
              color: Tuple[int, int, int], width: int, height: int):
    """
    Draw an anti-aliased 1px line (Xiaolin Wu style, clipped to the canvas).

    On a low-resolution LED panel a hard-stepped diagonal reads as jagged
    stairs; splitting each step's brightness across the two nearest pixels
    makes strokes look smooth and calm.
    """
    steep = abs(y1 - y0) > abs(x1 - x0)
    if steep:
        x0, y0, x1, y1 = y0, x0, y1, x1
    if x0 > x1:
        x0, x1, y0, y1 = x1, x0, y1, y0

    dx = x1 - x0
    gradient = (y1 - y0) / dx if dx else 0.0

    def plot(px: int, py: int, brightness: float):
        if steep:
            px, py = py, px
        if 0 <= px < width and 0 <= py < height and brightness > 0.05:
            canvas.SetPixel(px, py, *scale(color, brightness))

    y = y0
    for x in range(int(round(x0)), int(round(x1)) + 1):
        fy = y0 + gradient * (x - x0)
        base = math.floor(fy)
        frac = fy - base
        plot(x, int(base), 1.0 - frac)
        plot(x, int(base) + 1, frac)


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
    """Trim long content so a scroll pass stays a sensible length.

    Uses "..." rather than the single "…" character: the ellipsis is not
    in Latin-1, so it would come out of sanitize() as "?" on the panel.
    """
    text = " ".join(text.split())  # Collapse newlines/whitespace runs
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 3].rstrip() + "..."
