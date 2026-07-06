"""Tests for nodeice_board.database."""

import pytest

from nodeice_board.database import Database


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    yield database
    database.close()


def test_create_and_get_post(db):
    post_id = db.create_post("Hello mesh", "!node1", "Alice")
    post = db.get_post(post_id)
    assert post["content"] == "Hello mesh"
    assert post["author_id"] == "!node1"
    assert post["author_name"] == "Alice"
    assert post["visible"] is True


def test_get_missing_post(db):
    assert db.get_post(999) is None


def test_create_post_validation(db):
    with pytest.raises(ValueError):
        db.create_post("", "!node1")
    with pytest.raises(ValueError):
        db.create_post("   ", "!node1")
    with pytest.raises(ValueError):
        db.create_post("content", "")


def test_create_post_truncates_long_content(db):
    post_id = db.create_post("x" * 2000, "!node1")
    assert len(db.get_post(post_id)["content"]) == 1000


def test_get_recent_posts(db):
    for i in range(7):
        db.create_post(f"post {i}", "!node1")
    posts = db.get_recent_posts(limit=5)
    assert len(posts) == 5


def test_comments(db):
    post_id = db.create_post("a post", "!node1")
    db.create_comment(post_id, "first!", "!node2", "Bob")
    db.create_comment(post_id, "second", "!node3")
    comments = db.get_comments_for_post(post_id)
    assert [c["content"] for c in comments] == ["first!", "second"]


def test_comment_validation(db):
    post_id = db.create_post("a post", "!node1")
    with pytest.raises(ValueError):
        db.create_comment(post_id, "", "!node2")
    with pytest.raises(ValueError):
        db.create_comment(-1, "hi", "!node2")


def test_expiration(db):
    post_id = db.create_post("old post", "!node1")
    fresh_id = db.create_post("fresh post", "!node1")

    # Backdate the first post by 10 days
    conn = db.get_connection()
    conn.execute(
        "UPDATE posts SET created_at = datetime('now', '-10 days') WHERE id = ?",
        (post_id,),
    )
    conn.commit()

    updated = db.mark_expired_posts_as_invisible(days=7)
    assert updated == 1
    assert db.get_post(post_id) is None  # No longer visible
    assert db.get_post(fresh_id) is not None
    # Expired posts still count toward the all-time total
    assert db.get_total_posts_count() == 2


def test_subscriptions_all_posts(db):
    assert db.subscribe_to_all_posts("!node1") is True
    assert db.subscribe_to_all_posts("!node1") is False  # Duplicate
    assert db.get_subscribers_for_all_posts() == ["!node1"]

    assert db.unsubscribe_from_all("!node1") == 1
    assert db.get_subscribers_for_all_posts() == []


def test_subscriptions_specific_post(db):
    post_id = db.create_post("a post", "!node1")
    assert db.subscribe_to_post("!node2", post_id) is True
    assert db.subscribe_to_post("!node2", post_id) is False  # Duplicate
    assert db.get_subscribers_for_post(post_id) == ["!node2"]

    assert db.unsubscribe_from_post("!node2", post_id) is True
    assert db.unsubscribe_from_post("!node2", post_id) is False
    assert db.get_subscribers_for_post(post_id) == []


def test_subscribe_to_missing_post(db):
    with pytest.raises(ValueError):
        db.subscribe_to_post("!node1", 42)


def test_get_user_subscriptions(db):
    post_id = db.create_post("a post", "!node1")
    db.subscribe_to_all_posts("!node2")
    db.subscribe_to_post("!node2", post_id)

    subs = db.get_user_subscriptions("!node2")
    assert len(subs) == 2
    assert any(s["all_posts"] for s in subs)
    assert any(s["post_id"] == post_id for s in subs)
