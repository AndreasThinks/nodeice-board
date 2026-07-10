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
    MESH_GREEN, AMBER, SOFT_WHITE, DIM_GREY, NIGHT_GREEN,
    Marquee, ScrollLine, scale, pulse, ellipsize,
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
            text = (f"Meshtastic notice board  ·  DM !post <msg> to post  ·  "
                    f"!help for commands  ·  {posts} on the board  ·  ")
        else:
            text = "waiting for the notice board database ...   "
        self.marquee.set_text(sanitize(text))


def draw_chrome(canvas, ctx: RenderContext):
    """Wordmark, accent line and marquee - shared by the calm scenes."""
    render.draw_text_centered(ctx.gfx, canvas, ctx.font_small, HEADER_BASELINE,
                              MESH_GREEN, "NODEICE", ctx.width)
    render.draw_accent_line(ctx.gfx, canvas, ACCENT_Y, ctx.width, ctx.t)
    ctx.marquee.draw(ctx.gfx, canvas, MARQUEE_BASELINE, DIM_GREY)


def draw_card(canvas, ctx: RenderContext, label: str, value: str,
              color, brightness: float = 1.0):
    """A label + value card in the middle area."""
    render.draw_text_centered(ctx.gfx, canvas, ctx.font_small, CARD_LABEL_BASELINE,
                              scale(DIM_GREY, brightness), sanitize(label), ctx.width)
    render.draw_text_centered(ctx.gfx, canvas, ctx.font_big, CARD_VALUE_BASELINE,
                              scale(color, brightness), sanitize(value), ctx.width)


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
        return [
            ("POSTS", str(ctx.visible_posts), MESH_GREEN),
            ("TIME", datetime.now().strftime("%H:%M"), SOFT_WHITE),
            ("ALL TIME", str(ctx.total_posts), AMBER),
        ]

    def step(self, dt: float, ctx: RenderContext):
        self.elapsed += dt
        if self.elapsed >= self.CARD_SECONDS:
            self.elapsed = 0.0
            self.card_index += 1

    def draw(self, canvas, ctx: RenderContext):
        draw_chrome(canvas, ctx)
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
                body=sanitize(ellipsize(p.content, 60) + f"  - {p.author}"),
                prefix=sanitize(f"#{p.post_id} "),
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
            self._lines[self._index].draw(ctx.gfx, canvas, SCROLL_BASELINE,
                                          SOFT_WHITE, prefix_color=AMBER)


class AlertScene(Scene):
    """
    New post / comment: an expanding ring burst, a pulsing banner, then
    the message itself scrolls across twice.
    """

    RINGS_SECONDS = 0.9
    BANNER_SECONDS = 1.4

    def __init__(self, ctx: RenderContext, event):
        if isinstance(event, NewComment):
            self.banner_word = "REPLY"
        else:
            self.banner_word = "POST"
        body = sanitize(ellipsize(event.content, 120) + f"  - {event.author}")
        prefix = sanitize(f"#{event.post_id} ")
        self._scroll = ScrollLine(ctx.font_big, ctx.width, body=body, prefix=prefix,
                                  speed_px_s=26.0, passes=2)
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
            self._scroll.draw(ctx.gfx, canvas, SCROLL_BASELINE,
                              SOFT_WHITE, prefix_color=AMBER)

    def _draw_rings(self, canvas, ctx: RenderContext):
        """Expanding concentric rings in Meshtastic green, like a radio ping."""
        progress = self.elapsed / self.RINGS_SECONDS
        cx = (ctx.width - 1) / 2
        cy = (ctx.height - 1) / 2
        max_radius = math.hypot(cx, cy) + 4
        lead = progress * max_radius
        for trail, brightness in ((0, 1.0), (3, 0.45), (6, 0.18)):
            radius = lead - trail
            render.draw_ring(canvas, cx, cy, radius,
                             scale(MESH_GREEN, brightness), ctx.width, ctx.height)
        if progress < 0.25:
            canvas.SetPixel(int(cx), int(cy), *MESH_GREEN)

    def _draw_banner(self, canvas, ctx: RenderContext):
        """'NEW POST' with a soft pulse and a few background twinkles."""
        t = self.elapsed - self.RINGS_SECONDS
        brightness = pulse(t, period=0.9, low=0.55, high=1.0)

        # Deterministic sparse twinkles (no randomness = no flicker artifacts)
        for i in range(7):
            x = (i * 13 + int(t * 10) * 7) % ctx.width
            y = (i * 7 + int(t * 10) * 5) % ctx.height
            canvas.SetPixel(x, y, *scale(NIGHT_GREEN, 0.8))

        render.draw_text_centered(ctx.gfx, canvas, ctx.font_big, 14,
                                  scale(AMBER, brightness), "NEW", ctx.width)
        render.draw_text_centered(ctx.gfx, canvas, ctx.font_big, 26,
                                  scale(SOFT_WHITE, brightness), self.banner_word, ctx.width)


class BrandScene(Scene):
    """
    Periodic ident: the Meshtastic mesh "M" traces itself across the
    panel node by node, holds with gently pulsing nodes, then shrinks to
    the top while "Meshtastic Nodeice Board" scrolls through underneath.
    """

    TRACE_SECONDS = 1.4
    HOLD_SECONDS = 2.2

    # The mesh "M" as polyline vertices in a unit square (y=0 at the top)
    LOGO_VERTICES = [
        (0.05, 0.90), (0.28, 0.10), (0.50, 0.62), (0.72, 0.10), (0.95, 0.90),
    ]

    def __init__(self, ctx: RenderContext):
        self._scroll = ScrollLine(ctx.font_big, ctx.width,
                                  body=sanitize("Nodeice Board"),
                                  prefix=sanitize("Meshtastic "),
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
            self._scroll.draw(ctx.gfx, canvas, 26, SOFT_WHITE,
                              prefix_color=MESH_GREEN)

    def _draw_logo(self, canvas, ctx: RenderContext,
                   x0: int, y0: int, w: int, h: int, progress: float):
        """Draw the mesh-M scaled into a rect, traced up to `progress`."""
        points = [(x0 + vx * w, y0 + vy * h) for vx, vy in self.LOGO_VERTICES]
        lengths = [math.hypot(bx - ax, by - ay)
                   for (ax, ay), (bx, by) in zip(points, points[1:])]
        remaining = progress * sum(lengths)

        node_color = scale(MESH_GREEN, pulse(ctx.t, period=1.8, low=0.7, high=1.0))
        line_color = scale(MESH_GREEN, 0.55)

        self._draw_node(canvas, ctx, points[0], node_color)
        for (ax, ay), (bx, by), length in zip(points, points[1:], lengths):
            if remaining <= 0:
                break
            p = min(1.0, remaining / length)
            render.draw_line(canvas, ax, ay, ax + (bx - ax) * p, ay + (by - ay) * p,
                             line_color, ctx.width, ctx.height)
            if p >= 1.0:
                self._draw_node(canvas, ctx, (bx, by), node_color)
            remaining -= length

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
