"""
Scenes for the matrix display.

A scene owns the whole frame while active. The app steps exactly one
scene per frame (single render thread — no canvas races) and switches
scenes based on watcher events:

- IdleScene:    wordmark + rotating info card + call-to-action marquee
- TickerScene:  recent posts scrolling through the card area
- AlertScene:   ring burst -> banner -> the new post/comment scrolls twice
- BrandScene:   periodic ident: the Meshtastic mesh-M plus the board name
- WaitingScene: shown until the board database is reachable

Layout (32px tall reference; positions are baselines):

    row  0-4   NODEICE wordmark (4x6 caps)
    row  6     animated accent line
    rows 8-25  card / scroll area (6x10)
    rows 26-31 marquee (4x6)
"""

import math
import time
from datetime import datetime
from typing import List, Optional

from nodeice_board.matrix import render
from nodeice_board.matrix.render import (
    MESH_GREEN, TEAL, AMBER, SOFT_WHITE, DIM_GREY,
    Marquee, ScrollLine, scale, fade, pulse, ellipsize,
)
from nodeice_board.matrix.watcher import NewPost, NewComment

# The 4x6 font's caps extend 5 rows above the baseline (CAP_HEIGHT 5),
# so a baseline of 5 puts the wordmark exactly in rows 0-4.
HEADER_BASELINE = 5
ACCENT_Y = 6
CARD_LABEL_BASELINE = 14
CARD_VALUE_BASELINE = 23
SCROLL_BASELINE = 20
MARQUEE_BASELINE = 30


def sanitize(text: str) -> str:
    """Replace characters the bundled Latin-1 BDF fonts can't render."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


class RenderContext:
    """Shared state the scenes draw from."""

    def __init__(self, gfx, font_small, font_big, width: int, height: int):
        self.gfx = gfx
        self.font_small = font_small
        self.font_big = font_big
        self.width = width
        self.height = height
        self.visible_posts = 0
        self.total_posts = 0
        self.recent_posts: List[NewPost] = []
        self.marquee = Marquee(font_small, width)
        self.t = 0.0  # Monotonic scene-independent clock for ambient animation

    def step(self, dt: float):
        self.t += dt
        self.marquee.step(dt)

    def update_marquee_text(self, db_available: bool = True):
        if db_available:
            n = self.visible_posts
            posts = "1 post" if n == 1 else f"{n} posts"
            # The commands are the call to action, so they get color while
            # the surrounding text stays in the default muted grey
            command = scale(MESH_GREEN, 0.7)
            segments = [
                ("Meshtastic notice board  ·  DM ", None),
                ("!post <msg>", command),
                (" to post  ·  ", None),
                ("!help", command),
                (f" for commands  ·  {posts} on the board  ·  ", None),
            ]
        else:
            segments = [("waiting for the notice board database ...   ", None)]
        self.marquee.set_segments([(sanitize(text), color) for text, color in segments])


def draw_chrome(canvas, ctx: RenderContext):
    """Wordmark, accent line and marquee - shared by the calm scenes."""
    render.draw_text_centered(ctx.gfx, canvas, ctx.font_small, HEADER_BASELINE,
                              MESH_GREEN, "NODEICE", ctx.width)
    render.draw_accent_line(ctx.gfx, canvas, ACCENT_Y, ctx.width, ctx.t)
    ctx.marquee.draw(ctx.gfx, canvas, MARQUEE_BASELINE, DIM_GREY)


def draw_card(canvas, ctx: RenderContext, label: str, value: str,
              color, brightness: float = 1.0):
    """A label + value card in the middle area. Brightness fades are
    gamma-corrected so crossfades and pulses look smooth on LEDs."""
    render.draw_text_centered(ctx.gfx, canvas, ctx.font_small, CARD_LABEL_BASELINE,
                              fade(DIM_GREY, brightness), sanitize(label), ctx.width)
    render.draw_text_centered(ctx.gfx, canvas, ctx.font_big, CARD_VALUE_BASELINE,
                              fade(color, brightness), sanitize(value), ctx.width)


class Scene:
    """Base scene. `done` scenes are replaced by the app on the next frame."""
    done = False

    def step(self, dt: float, ctx: RenderContext):
        pass

    def draw(self, canvas, ctx: RenderContext):
        raise NotImplementedError


class IdleScene(Scene):
    """Rotating info cards with a gentle crossfade between them."""

    CARD_SECONDS = 5.0
    FADE_SECONDS = 0.5

    def __init__(self):
        self.elapsed = 0.0
        self.card_index = 0

    def _cards(self, ctx: RenderContext):
        # Blinking colon makes the clock feel alive (fonts are monospaced,
        # so swapping ":" for " " doesn't shift the centering)
        clock = datetime.now().strftime("%H:%M" if int(ctx.t) % 2 == 0 else "%H %M")
        cards = [
            ("POSTS", str(ctx.visible_posts), MESH_GREEN),
            ("TIME", clock, SOFT_WHITE),
            ("ALL TIME", str(ctx.total_posts), AMBER),
        ]
        if ctx.recent_posts:
            # Tease the newest post's author, trimmed to the panel width
            # (the big font is 6px per character)
            max_chars = max(3, ctx.width // 6)
            cards.append(("LATEST", ellipsize(ctx.recent_posts[0].author, max_chars), TEAL))
        return cards

    def step(self, dt: float, ctx: RenderContext):
        self.elapsed += dt
        if self.elapsed >= self.CARD_SECONDS:
            self.elapsed = 0.0
            self.card_index += 1

    def _draw_twinkles(self, canvas, ctx: RenderContext):
        """A few slow ambient twinkles so the card area never looks frozen."""
        for i in range(6):
            x = (i * 23 + 5) % ctx.width
            y = 9 + (i * 7) % 15  # Stay inside the card area rows
            brightness = pulse(ctx.t + i * 1.1, period=3.5 + i * 0.3, low=0.0, high=0.4)
            canvas.SetPixel(x, y, *fade(MESH_GREEN, brightness))

    def draw(self, canvas, ctx: RenderContext):
        draw_chrome(canvas, ctx)
        self._draw_twinkles(canvas, ctx)
        cards = self._cards(ctx)
        current = cards[self.card_index % len(cards)]
        previous = cards[(self.card_index - 1) % len(cards)]

        if self.elapsed < self.FADE_SECONDS and self.card_index > 0:
            # Crossfade: previous fades out while the new card fades in
            p = self.elapsed / self.FADE_SECONDS
            draw_card(canvas, ctx, previous[0], previous[1], previous[2], brightness=1.0 - p)
            draw_card(canvas, ctx, current[0], current[1], current[2], brightness=p)
        else:
            draw_card(canvas, ctx, current[0], current[1], current[2])


class TickerScene(Scene):
    """Scrolls the most recent posts through the card area, one at a time."""

    def __init__(self, ctx: RenderContext, posts: List[NewPost]):
        self._lines = [
            ScrollLine(
                ctx.font_big, ctx.width,
                segments=[
                    (sanitize(f"#{p.post_id} "), AMBER),
                    (sanitize(ellipsize(p.content, 60)), SOFT_WHITE),
                    (sanitize(f"  - {p.author}"), MESH_GREEN),
                ],
                speed_px_s=24.0,
            )
            for p in posts
        ]
        self._index = 0

    @property
    def done(self) -> bool:
        return self._index >= len(self._lines)

    def step(self, dt: float, ctx: RenderContext):
        if self.done:
            return
        line = self._lines[self._index]
        line.step(dt)
        if line.done:
            self._index += 1

    def draw(self, canvas, ctx: RenderContext):
        draw_chrome(canvas, ctx)
        if not self.done:
            self._lines[self._index].draw(ctx.gfx, canvas, SCROLL_BASELINE)


class AlertScene(Scene):
    """
    New post / comment: an expanding ring burst, a pulsing banner, then
    the message itself scrolls across twice.
    """

    RINGS_SECONDS = 0.9
    BANNER_SECONDS = 1.4

    def __init__(self, ctx: RenderContext, event):
        # Color language: green announces a new post, amber a reply, so a
        # passer-by can tell the event type from across the room
        if isinstance(event, NewComment):
            self.banner_word = "REPLY"
            self.accent = AMBER
        else:
            self.banner_word = "POST"
            self.accent = MESH_GREEN
        self._scroll = ScrollLine(
            ctx.font_big, ctx.width,
            segments=[
                (sanitize(f"#{event.post_id} "), AMBER),
                (sanitize(ellipsize(event.content, 120)), SOFT_WHITE),
                (sanitize(f"  - {event.author}"), MESH_GREEN),
            ],
            speed_px_s=26.0, passes=2,
        )
        self.elapsed = 0.0

    @property
    def done(self) -> bool:
        return (self.elapsed >= self.RINGS_SECONDS + self.BANNER_SECONDS
                and self._scroll.done)

    def step(self, dt: float, ctx: RenderContext):
        self.elapsed += dt
        if self.elapsed >= self.RINGS_SECONDS + self.BANNER_SECONDS:
            self._scroll.step(dt)

    def draw(self, canvas, ctx: RenderContext):
        if self.elapsed < self.RINGS_SECONDS:
            self._draw_rings(canvas, ctx)
        elif self.elapsed < self.RINGS_SECONDS + self.BANNER_SECONDS:
            self._draw_banner(canvas, ctx)
        else:
            draw_chrome(canvas, ctx)
            self._scroll.draw(ctx.gfx, canvas, SCROLL_BASELINE)

    def _draw_rings(self, canvas, ctx: RenderContext):
        """Expanding concentric rings in the event color, like a radio ping."""
        progress = self.elapsed / self.RINGS_SECONDS
        cx = (ctx.width - 1) / 2
        cy = (ctx.height - 1) / 2
        max_radius = math.hypot(cx, cy) + 4
        lead = progress * max_radius
        for trail, brightness in ((0, 1.0), (3, 0.6), (6, 0.35)):
            radius = lead - trail
            render.draw_ring(canvas, cx, cy, radius,
                             fade(self.accent, brightness), ctx.width, ctx.height)
        if progress < 0.25:
            canvas.SetPixel(int(cx), int(cy), *self.accent)

    def _draw_banner(self, canvas, ctx: RenderContext):
        """'NEW POST' / 'NEW REPLY' with a soft pulse and background twinkles."""
        t = self.elapsed - self.RINGS_SECONDS
        brightness = pulse(t, period=0.9, low=0.55, high=1.0)

        # Deterministic sparse twinkles (no randomness = no flicker artifacts),
        # tinted to match the event color
        for i in range(7):
            x = (i * 13 + int(t * 10) * 7) % ctx.width
            y = (i * 7 + int(t * 10) * 5) % ctx.height
            canvas.SetPixel(x, y, *scale(self.accent, 0.2))

        render.draw_text_centered(ctx.gfx, canvas, ctx.font_big, 14,
                                  fade(self.accent, brightness), "NEW", ctx.width)
        render.draw_text_centered(ctx.gfx, canvas, ctx.font_big, 26,
                                  fade(SOFT_WHITE, brightness), self.banner_word, ctx.width)


class BrandScene(Scene):
    """
    Periodic ident: the Meshtastic mesh "M" traces itself across the
    panel node by node, holds with gently pulsing nodes, then shrinks to
    the top while "Meshtastic Nodeice Board" scrolls through underneath.
    """

    TRACE_SECONDS = 1.6
    HOLD_SECONDS = 2.2
    PING_SECONDS = 0.55  # Ring burst as each mesh node lights up

    # The mesh "M" as polyline vertices in a unit square (y=0 at the top)
    LOGO_VERTICES = [
        (0.06, 0.86), (0.29, 0.14), (0.50, 0.58), (0.71, 0.14), (0.94, 0.86),
    ]

    def __init__(self, ctx: RenderContext):
        self._scroll = ScrollLine(ctx.font_big, ctx.width,
                                  segments=[
                                      (sanitize("Meshtastic "), MESH_GREEN),
                                      (sanitize("Nodeice Board"), SOFT_WHITE),
                                  ],
                                  speed_px_s=24.0)
        self.elapsed = 0.0

    @property
    def done(self) -> bool:
        return (self.elapsed >= self.TRACE_SECONDS + self.HOLD_SECONDS
                and self._scroll.done)

    def step(self, dt: float, ctx: RenderContext):
        self.elapsed += dt
        if self.elapsed >= self.TRACE_SECONDS + self.HOLD_SECONDS:
            self._scroll.step(dt)

    def draw(self, canvas, ctx: RenderContext):
        if self.elapsed < self.TRACE_SECONDS:
            progress = self.elapsed / self.TRACE_SECONDS
            self._draw_logo(canvas, ctx, 3, 4, ctx.width - 7, 22, progress)
        elif self.elapsed < self.TRACE_SECONDS + self.HOLD_SECONDS:
            self._draw_logo(canvas, ctx, 3, 4, ctx.width - 7, 22, 1.0)
        else:
            # Mini logo up top, the name scrolling through the big font
            self._draw_logo(canvas, ctx, 8, 2, ctx.width - 17, 10, 1.0)
            self._scroll.draw(ctx.gfx, canvas, 26)

    def _draw_logo(self, canvas, ctx: RenderContext,
                   x0: int, y0: int, w: int, h: int, progress: float):
        """
        Draw the mesh-M scaled into a rect, traced up to `progress`.

        A white spark leads the trace, and each vertex fires a brief ring
        "ping" (timed off self.elapsed) as the trace reaches it.
        """
        points = [(x0 + vx * w, y0 + vy * h) for vx, vy in self.LOGO_VERTICES]
        lengths = [math.hypot(bx - ax, by - ay)
                   for (ax, ay), (bx, by) in zip(points, points[1:])]
        total = sum(lengths)
        target = progress * total

        node_color = fade(MESH_GREEN, pulse(ctx.t, period=1.8, low=0.8, high=1.0))
        line_color = scale(MESH_GREEN, 0.7)

        remaining = target
        tip = points[0]
        for (ax, ay), (bx, by), length in zip(points, points[1:], lengths):
            if remaining <= 0:
                break
            p = min(1.0, remaining / length)
            tip = (ax + (bx - ax) * p, ay + (by - ay) * p)
            render.draw_line(canvas, ax, ay, tip[0], tip[1],
                             line_color, ctx.width, ctx.height)
            remaining -= length

        # Nodes and their pings, timed by when the trace reaches each vertex
        travelled = 0.0
        for i, point in enumerate(points):
            if travelled > target:
                break
            self._draw_node(canvas, ctx, point, node_color)

            ping_age = self.elapsed - (travelled / total) * self.TRACE_SECONDS
            if 0.0 <= ping_age < self.PING_SECONDS:
                ping_fade = 1.0 - ping_age / self.PING_SECONDS
                radius = 1.5 + (1.0 - ping_fade) * 5.0
                render.draw_ring(canvas, point[0], point[1], radius,
                                 fade(MESH_GREEN, 0.7 * ping_fade),
                                 ctx.width, ctx.height)
            if i < len(lengths):
                travelled += lengths[i]

        # A bright spark leads the trace while it is still drawing
        if progress < 1.0:
            canvas.SetPixel(int(round(tip[0])), int(round(tip[1])), *SOFT_WHITE)

    @staticmethod
    def _draw_node(canvas, ctx: RenderContext, point, color):
        """A small plus-shaped mesh node marker."""
        x, y = int(round(point[0])), int(round(point[1]))
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
            px, py = x + dx, y + dy
            if 0 <= px < ctx.width and 0 <= py < ctx.height:
                canvas.SetPixel(px, py, *color)


class WaitingScene(Scene):
    """Shown while the board database is unreachable."""

    def __init__(self):
        self.elapsed = 0.0

    def step(self, dt: float, ctx: RenderContext):
        self.elapsed += dt

    def draw(self, canvas, ctx: RenderContext):
        draw_chrome(canvas, ctx)
        brightness = pulse(self.elapsed, period=2.4, low=0.35, high=0.9)
        draw_card(canvas, ctx, "STATUS", "WAIT", AMBER, brightness=brightness)
