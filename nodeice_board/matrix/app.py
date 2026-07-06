"""
The matrix display application: one render thread, event-driven scenes.

The render loop is the only thing that touches the matrix, which avoids
the canvas races a multi-threaded design invites. Watcher events arrive
on a queue and are drained once per frame.
"""

import os
import queue
import time
import logging
from collections import deque
from typing import Optional

from nodeice_board.matrix.scenes import (
    RenderContext, IdleScene, TickerScene, AlertScene, WaitingScene,
)
from nodeice_board.matrix.watcher import (
    BoardWatcher, Stats, NewPost, NewComment, RecentPosts, DbStatus,
)

logger = logging.getLogger("NodeiceMatrix")

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")


def load_fonts(gfx):
    """Load the bundled BDF fonts (4x6 for labels, 6x10 for content)."""
    font_small = gfx.Font()
    font_small.LoadFont(os.path.join(FONT_DIR, "4x6.bdf"))
    font_big = gfx.Font()
    font_big.LoadFont(os.path.join(FONT_DIR, "6x10.bdf"))
    return font_small, font_big


class MatrixApp:
    """Owns the render loop, the scene state machine, and the watcher."""

    FPS = 30
    TICKER_EVERY_SECONDS = 45.0
    MAX_PENDING_ALERTS = 4

    def __init__(self, matrix, gfx, db_path: str, poll_interval: float = 2.0):
        self.matrix = matrix
        self.gfx = gfx
        font_small, font_big = load_fonts(gfx)
        self.ctx = RenderContext(gfx, font_small, font_big,
                                 matrix.width, matrix.height)
        self.events: "queue.Queue" = queue.Queue()
        self.watcher = BoardWatcher(db_path, self.events, poll_interval=poll_interval)

        self.db_available = False
        self.alerts = deque(maxlen=self.MAX_PENDING_ALERTS)
        self.idle_scene = IdleScene()
        self.scene = WaitingScene()
        self._next_ticker = time.monotonic() + self.TICKER_EVERY_SECONDS
        self.running = False

        self.ctx.update_marquee_text(db_available=False)

    # -- Event handling --------------------------------------------------

    def _drain_events(self):
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                return
            if isinstance(event, Stats):
                self.ctx.visible_posts = event.visible_posts
                self.ctx.total_posts = event.total_posts
                self.ctx.update_marquee_text(db_available=self.db_available)
            elif isinstance(event, RecentPosts):
                self.ctx.recent_posts = event.posts
            elif isinstance(event, (NewPost, NewComment)):
                self.alerts.append(event)
            elif isinstance(event, DbStatus):
                self.db_available = event.available
                self.ctx.update_marquee_text(db_available=event.available)

    # -- Scene selection ---------------------------------------------------

    def _defer_ticker(self):
        self._next_ticker = time.monotonic() + self.TICKER_EVERY_SECONDS

    def _choose_scene(self):
        if not self.db_available:
            if not isinstance(self.scene, WaitingScene):
                self.scene = WaitingScene()
            return

        # Alerts preempt the calm scenes (but never an alert mid-animation)
        if self.alerts and not isinstance(self.scene, AlertScene):
            self.scene = AlertScene(self.ctx, self.alerts.popleft())
            self._defer_ticker()
            return

        if self.scene.done or isinstance(self.scene, WaitingScene):
            if self.alerts:
                self.scene = AlertScene(self.ctx, self.alerts.popleft())
                self._defer_ticker()
            else:
                self.scene = self.idle_scene
            return

        # Periodically show the recent-posts ticker while idle
        if (isinstance(self.scene, IdleScene)
                and self.ctx.recent_posts
                and time.monotonic() >= self._next_ticker):
            self.scene = TickerScene(self.ctx, self.ctx.recent_posts)
            self._defer_ticker()

    # -- Main loop ----------------------------------------------------------

    def run(self, duration: Optional[float] = None):
        """
        Run the display until stop() is called (or `duration` seconds pass,
        used for smoke tests).
        """
        self.running = True
        self.watcher.start()

        canvas = self.matrix.CreateFrameCanvas()
        frame_seconds = 1.0 / self.FPS
        started = time.monotonic()
        last_frame = started

        logger.info(f"Matrix display running at {self.matrix.width}x{self.matrix.height}")
        try:
            while self.running:
                now = time.monotonic()
                if duration is not None and now - started >= duration:
                    break
                # Clamp dt so a stall doesn't teleport animations
                dt = min(now - last_frame, 0.1)
                last_frame = now

                self._drain_events()
                self._choose_scene()

                self.ctx.step(dt)
                self.scene.step(dt, self.ctx)

                canvas.Clear()
                self.scene.draw(canvas, self.ctx)
                canvas = self.matrix.SwapOnVSync(canvas)

                elapsed = time.monotonic() - now
                if elapsed < frame_seconds:
                    time.sleep(frame_seconds - elapsed)
        finally:
            self.running = False
            self.watcher.stop()
            self.watcher.join(timeout=5)
            try:
                self.matrix.Clear()
            except Exception:
                pass
            logger.info("Matrix display stopped")

    def stop(self):
        self.running = False
