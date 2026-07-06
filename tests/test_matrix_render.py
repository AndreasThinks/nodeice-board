"""Tests for the matrix rendering primitives and scenes."""

import pytest

from nodeice_board.matrix import render
from nodeice_board.matrix.render import Marquee, ScrollLine, ellipsize, scale, lerp, pulse
from nodeice_board.matrix.scenes import (
    RenderContext, IdleScene, TickerScene, AlertScene, WaitingScene, sanitize,
)
from nodeice_board.matrix.watcher import NewPost, NewComment

from tests.matrix_fakes import FakeGraphics, FakeFont, FakeCanvas


@pytest.fixture
def ctx():
    context = RenderContext(FakeGraphics(), FakeFont(), FakeFont(), 32, 32)
    context.visible_posts = 3
    context.total_posts = 10
    context.update_marquee_text()
    return context


# -- Primitives ----------------------------------------------------------------

def test_scale_clamps():
    assert scale((100, 200, 50), 0.5) == (50, 100, 25)
    assert scale((100, 200, 50), 2.0) == (100, 200, 50)
    assert scale((100, 200, 50), -1.0) == (0, 0, 0)


def test_lerp_endpoints():
    assert lerp((0, 0, 0), (100, 100, 100), 0.0) == (0, 0, 0)
    assert lerp((0, 0, 0), (100, 100, 100), 1.0) == (100, 100, 100)


def test_pulse_stays_in_range():
    for t in [0, 0.3, 1.1, 2.7, 100.0]:
        assert 0.35 <= pulse(t, low=0.35, high=1.0) <= 1.0


def test_ellipsize():
    assert ellipsize("short", 20) == "short"
    result = ellipsize("x" * 300, 100)
    assert len(result) <= 100
    assert result.endswith("…")
    # Newlines are collapsed so scrolling text stays on one line
    assert "\n" not in ellipsize("line one\nline two", 50)


def test_sanitize_replaces_non_latin1():
    assert sanitize("hello") == "hello"
    assert "?" in sanitize("pin 📌 emoji")
    assert sanitize("café") == "café"  # Latin-1 chars survive


def test_marquee_wraps_seamlessly():
    marquee = Marquee(FakeFont(), width=32, speed_px_s=10, gap_px=8)
    marquee.set_text("HELLO")  # 20px + 8 gap = 28px span
    for _ in range(100):
        marquee.step(0.1)
        assert 0 <= marquee.offset < 28


def test_marquee_text_swap_keeps_position():
    marquee = Marquee(FakeFont(), width=32)
    marquee.set_text("AAAA BBBB CCCC")
    marquee.step(0.5)
    offset = marquee.offset
    marquee.set_text("AAAA BBBB CCCD")
    assert marquee.offset == offset


def test_scroll_line_completes_passes():
    line = ScrollLine(FakeFont(), width=32, body="HELLO WORLD", prefix="#1 ",
                      speed_px_s=100, passes=2)
    steps = 0
    while not line.done and steps < 1000:
        line.step(0.1)
        steps += 1
    assert line.done
    assert line.completed == 2


def test_scroll_line_draws_prefix_and_body():
    gfx = FakeGraphics()
    canvas = FakeCanvas()
    line = ScrollLine(FakeFont(), width=32, body="content", prefix="#5 ")
    line.draw(gfx, canvas, 20, (255, 255, 255), prefix_color=(255, 170, 40))
    assert canvas.drawn_strings() == ["#5 ", "content"]
    assert canvas.texts[0]["color"] == (255, 170, 40)


# -- Scenes ---------------------------------------------------------------------

def test_idle_scene_rotates_cards(ctx):
    scene = IdleScene()
    canvas = FakeCanvas()
    scene.draw(canvas, ctx)
    assert "POSTS" in canvas.drawn_strings()
    assert "3" in canvas.drawn_strings()

    scene.step(5.1, ctx)  # Past CARD_SECONDS
    canvas.Clear()
    scene.draw(canvas, ctx)
    assert "TIME" in canvas.drawn_strings()


def test_idle_scene_draws_chrome(ctx):
    scene = IdleScene()
    canvas = FakeCanvas()
    scene.draw(canvas, ctx)
    strings = canvas.drawn_strings()
    assert "NODEICE" in strings
    assert any("!help" in s for s in strings)  # Marquee call-to-action
    # Accent line was drawn
    assert any(y == 6 for (_x, y) in canvas.pixels)


def test_ticker_scene_scrolls_all_posts(ctx):
    posts = [
        NewPost(post_id=1, content="first post", author="Alice"),
        NewPost(post_id=2, content="second post", author="Bob"),
    ]
    scene = TickerScene(ctx, posts)
    canvas = FakeCanvas()
    scene.draw(canvas, ctx)
    assert "#1 " in canvas.drawn_strings()

    steps = 0
    while not scene.done and steps < 5000:
        scene.step(0.1, ctx)
        steps += 1
    assert scene.done


def test_alert_scene_phases(ctx):
    event = NewPost(post_id=7, content="breaking news", author="Alice")
    scene = AlertScene(ctx, event)

    # Phase 1: rings (pixels, no text)
    canvas = FakeCanvas()
    scene.draw(canvas, ctx)
    assert canvas.pixels and not canvas.texts

    # Phase 2: banner
    scene.step(1.0, ctx)
    canvas.Clear()
    scene.draw(canvas, ctx)
    assert "NEW" in canvas.drawn_strings()
    assert "POST" in canvas.drawn_strings()

    # Phase 3: scrolling message
    scene.step(1.5, ctx)
    canvas.Clear()
    scene.draw(canvas, ctx)
    assert "#7 " in canvas.drawn_strings()
    assert any("breaking news" in s for s in canvas.drawn_strings())

    # Runs to completion
    steps = 0
    while not scene.done and steps < 5000:
        scene.step(0.1, ctx)
        steps += 1
    assert scene.done


def test_alert_scene_for_comment_says_reply(ctx):
    event = NewComment(post_id=3, content="me too", author="Bob")
    scene = AlertScene(ctx, event)
    scene.step(1.0, ctx)
    canvas = FakeCanvas()
    scene.draw(canvas, ctx)
    assert "REPLY" in canvas.drawn_strings()


def test_alert_scene_sanitizes_emoji(ctx):
    event = NewPost(post_id=1, content="hello 📌 world", author="Alice")
    scene = AlertScene(ctx, event)
    scene.step(3.0, ctx)
    canvas = FakeCanvas()
    scene.draw(canvas, ctx)
    for text in canvas.drawn_strings():
        text.encode("latin-1")  # Must not raise


def test_waiting_scene(ctx):
    ctx.update_marquee_text(db_available=False)
    scene = WaitingScene()
    scene.step(0.5, ctx)
    canvas = FakeCanvas()
    scene.draw(canvas, ctx)
    assert "WAIT" in canvas.drawn_strings()
    assert any("waiting" in s for s in canvas.drawn_strings())


def test_marquee_text_reflects_post_count(ctx):
    ctx.visible_posts = 1
    ctx.update_marquee_text()
    assert "1 post " in ctx.marquee.text or "1 post " in ctx.marquee.text + " "
    ctx.visible_posts = 12
    ctx.update_marquee_text()
    assert "12 posts" in ctx.marquee.text
