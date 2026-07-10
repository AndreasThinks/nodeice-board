"""Tests for the matrix display app: scene selection and the render loop."""

import pytest

from nodeice_board.config import get_matrix_config
from nodeice_board.database import Database
from nodeice_board.matrix.app import MatrixApp
from nodeice_board.matrix.scenes import (
    IdleScene, TickerScene, AlertScene, BrandScene, WaitingScene,
)
from nodeice_board.matrix.watcher import Stats, NewPost, RecentPosts, DbStatus

from tests.matrix_fakes import FakeCanvas, FakeGraphics, FakeMatrix


@pytest.fixture
def app(tmp_path, monkeypatch):
    # Fonts are loaded through the fake gfx module, so no BDF parsing happens
    application = MatrixApp(FakeMatrix(), FakeGraphics(), str(tmp_path / "board.db"))
    return application


def test_starts_waiting(app):
    assert isinstance(app.scene, WaitingScene)


def test_waiting_until_db_available(app):
    app._choose_scene()
    assert isinstance(app.scene, WaitingScene)

    app.events.put(DbStatus(available=True))
    app.events.put(Stats(visible_posts=2, total_posts=5))
    app._drain_events()
    app._choose_scene()
    assert isinstance(app.scene, IdleScene)
    assert app.ctx.visible_posts == 2


def test_new_post_preempts_idle(app):
    app.events.put(DbStatus(available=True))
    app._drain_events()
    app._choose_scene()

    app.events.put(NewPost(post_id=1, content="hello", author="Alice"))
    app._drain_events()
    app._choose_scene()
    assert isinstance(app.scene, AlertScene)


def test_alert_not_preempted_by_another_alert(app):
    app.events.put(DbStatus(available=True))
    app.events.put(NewPost(post_id=1, content="first", author="A"))
    app.events.put(NewPost(post_id=2, content="second", author="B"))
    app._drain_events()
    app._choose_scene()
    first_alert = app.scene
    assert isinstance(first_alert, AlertScene)

    app._choose_scene()
    assert app.scene is first_alert  # Still the same alert
    assert len(app.alerts) == 1  # Second alert queued


def test_alert_backlog_is_bounded(app):
    for i in range(10):
        app.events.put(NewPost(post_id=i, content=f"p{i}", author="A"))
    app._drain_events()
    assert len(app.alerts) <= app.MAX_PENDING_ALERTS


def test_db_loss_shows_waiting(app):
    app.events.put(DbStatus(available=True))
    app._drain_events()
    app._choose_scene()
    assert isinstance(app.scene, IdleScene)

    app.events.put(DbStatus(available=False))
    app._drain_events()
    app._choose_scene()
    assert isinstance(app.scene, WaitingScene)


def test_ticker_shown_when_due(app, monkeypatch):
    app.events.put(DbStatus(available=True))
    app.events.put(RecentPosts(posts=[NewPost(post_id=1, content="p", author="A")]))
    app._drain_events()
    app._choose_scene()
    assert isinstance(app.scene, IdleScene)

    app._next_ticker = 0  # Force the ticker to be due
    app._choose_scene()
    assert isinstance(app.scene, TickerScene)


def test_brand_scene_shown_when_due(app):
    app.events.put(DbStatus(available=True))
    app._drain_events()
    app._choose_scene()
    assert isinstance(app.scene, IdleScene)

    app._next_brand = 0  # Force the ident to be due
    app._choose_scene()
    assert isinstance(app.scene, BrandScene)


def test_brand_scene_runs_to_completion(app):
    scene = BrandScene(app.ctx)
    canvas = FakeCanvas()

    elapsed = 0.0
    while not scene.done and elapsed < 30.0:
        scene.step(1 / 30, app.ctx)
        app.ctx.step(1 / 30)
        scene.draw(canvas, app.ctx)
        elapsed += 1 / 30

    assert scene.done
    assert canvas.pixels  # The logo drew mesh nodes and lines
    drawn = " ".join(canvas.drawn_strings())
    assert "Meshtastic" in drawn and "Nodeice Board" in drawn


def test_full_loop_runs_headless(tmp_path):
    """End-to-end: real watcher thread + render loop against a real database."""
    db_path = str(tmp_path / "board.db")
    db = Database(db_path)
    db.create_post("a post already on the board", "!node1", "Alice")
    db.close()

    matrix = FakeMatrix()
    app = MatrixApp(matrix, FakeGraphics(), db_path, poll_interval=0.05)
    app.run(duration=0.5)

    assert matrix.swapped_frames > 5  # Frames were rendered
    assert matrix.cleared  # Display cleared on shutdown
    assert not app.watcher.is_alive()  # Watcher stopped


def test_matrix_config_defaults():
    config = get_matrix_config({})
    assert config["rows"] == 32
    assert config["cols"] == 32
    assert config["hardware_mapping"] == "adafruit-hat"
    assert 0 <= config["brightness"] <= 100


def test_matrix_config_overrides():
    config = get_matrix_config({
        "Matrix_display": {"Rows": 64, "Brightness": 80, "GPIO_Slowdown": 4}
    })
    assert config["rows"] == 64
    assert config["brightness"] == 80
    assert config["gpio_slowdown"] == 4
    assert config["cols"] == 32  # Untouched default
