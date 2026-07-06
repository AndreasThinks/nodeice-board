"""Tests for the matrix display's database watcher."""

import queue

import pytest

from nodeice_board.database import Database
from nodeice_board.matrix.watcher import (
    BoardWatcher, Stats, NewPost, NewComment, RecentPosts, DbStatus,
)


def drain(q):
    events = []
    while True:
        try:
            events.append(q.get_nowait())
        except queue.Empty:
            return events


def events_of(events, kind):
    return [e for e in events if isinstance(e, kind)]


@pytest.fixture
def board(tmp_path):
    db_path = str(tmp_path / "board.db")
    db = Database(db_path)
    yield db_path, db
    db.close()


def test_missing_db_reports_unavailable(tmp_path):
    q = queue.Queue()
    watcher = BoardWatcher(str(tmp_path / "nope.db"), q)
    watcher._poll_once()
    statuses = events_of(drain(q), DbStatus)
    assert statuses and statuses[0].available is False


def test_first_poll_does_not_replay_history(board):
    db_path, db = board
    db.create_post("existing post", "!node1")

    q = queue.Queue()
    watcher = BoardWatcher(db_path, q)
    watcher._poll_once()
    events = drain(q)

    assert not events_of(events, NewPost)  # No replay
    stats = events_of(events, Stats)[0]
    assert stats.visible_posts == 1
    assert events_of(events, DbStatus)[0].available is True


def test_new_post_detected(board):
    db_path, db = board
    q = queue.Queue()
    watcher = BoardWatcher(db_path, q)
    watcher._poll_once()
    drain(q)

    db.create_post("hot off the mesh", "!node2", "Alice")
    watcher._poll_once()
    new_posts = events_of(drain(q), NewPost)
    assert len(new_posts) == 1
    assert new_posts[0].content == "hot off the mesh"
    assert new_posts[0].author == "Alice"


def test_author_falls_back_to_node_id(board):
    db_path, db = board
    q = queue.Queue()
    watcher = BoardWatcher(db_path, q)
    watcher._poll_once()
    drain(q)

    db.create_post("anonymous-ish", "!node9")
    watcher._poll_once()
    assert events_of(drain(q), NewPost)[0].author == "!node9"


def test_new_comment_detected(board):
    db_path, db = board
    post_id = db.create_post("a post", "!node1")

    q = queue.Queue()
    watcher = BoardWatcher(db_path, q)
    watcher._poll_once()
    drain(q)

    db.create_comment(post_id, "great post", "!node2", "Bob")
    watcher._poll_once()
    comments = events_of(drain(q), NewComment)
    assert len(comments) == 1
    assert comments[0].post_id == post_id
    assert comments[0].author == "Bob"


def test_recent_posts_emitted(board):
    db_path, db = board
    for i in range(5):
        db.create_post(f"post {i}", "!node1")

    q = queue.Queue()
    watcher = BoardWatcher(db_path, q)
    watcher._poll_once()
    recent = events_of(drain(q), RecentPosts)[0]
    assert len(recent.posts) == 3  # Capped at 3
    assert recent.posts[0].content == "post 4"  # Newest first


def test_burst_of_posts_is_capped(board):
    db_path, db = board
    q = queue.Queue()
    watcher = BoardWatcher(db_path, q)
    watcher._poll_once()
    drain(q)

    for i in range(10):
        db.create_post(f"burst {i}", "!node1")
    watcher._poll_once()
    assert len(events_of(drain(q), NewPost)) <= 5


def test_db_appearing_later_recovers(tmp_path):
    db_path = str(tmp_path / "late.db")
    q = queue.Queue()
    watcher = BoardWatcher(db_path, q)

    watcher._poll_once()
    assert events_of(drain(q), DbStatus)[0].available is False

    db = Database(db_path)
    try:
        watcher._poll_once()
        events = drain(q)
        assert events_of(events, DbStatus)[0].available is True
        assert events_of(events, Stats)
    finally:
        db.close()


def test_watcher_is_read_only(board):
    """The watcher's connection must be unable to write to the board DB."""
    import sqlite3

    db_path, db = board
    q = queue.Queue()
    watcher = BoardWatcher(db_path, q)
    watcher._poll_once()

    conn = watcher._get_conn()
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("INSERT INTO posts (content, author_id) VALUES ('evil', 'x')")
