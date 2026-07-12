"""Tests for nodeice_board.command_handler."""

import pytest

from nodeice_board.database import Database
from nodeice_board.command_handler import CommandHandler


class FakeSender:
    """Captures messages the command handler tries to send."""

    def __init__(self):
        self.sent = []  # List of (message, destination)

    def __call__(self, message, destination):
        self.sent.append((message, destination))
        return True

    def messages_to(self, destination):
        return [m for m, d in self.sent if d == destination]


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    yield database
    database.close()


@pytest.fixture
def sender():
    return FakeSender()


@pytest.fixture
def handler(db, sender, monkeypatch):
    h = CommandHandler(database=db, send_message_callback=sender, config={})
    h.rate_limit_seconds = 0  # Disable rate limiting for tests
    monkeypatch.setattr("nodeice_board.command_handler.time.sleep", lambda s: None)
    return h


def test_help_command(handler, sender):
    assert handler.handle_message("!help", "!user1") is True
    combined = "\n".join(sender.messages_to("!user1"))
    assert "!post" in combined
    assert "!list" in combined


def test_help_essentials_fit_one_packet(handler, sender):
    """Each help message must fit a single LoRa packet, with !post in the
    first one, so 'how to post' survives even if later packets are lost."""
    handler.handle_message("!help", "!user1")
    messages = sender.messages_to("!user1")
    assert len(messages) == 2
    assert "!post" in messages[0]
    for message in messages:
        assert len(message.encode("utf-8")) <= 200


def test_post_command(handler, sender, db):
    assert handler.handle_message("!post Lost cat in sector 7", "!user1") is True
    assert "Post #1 created" in sender.messages_to("!user1")[0]
    assert db.get_post(1)["content"] == "Lost cat in sector 7"


def test_list_command(handler, sender, db):
    db.create_post("first", "!user1")
    db.create_post("second", "!user2")
    assert handler.handle_message("!list", "!user3") is True
    messages = sender.messages_to("!user3")
    # One merged message: the interface packs it into minimal packets
    assert len(messages) == 1
    assert "first" in messages[0]
    assert "second" in messages[0]


def test_list_command_empty(handler, sender):
    assert handler.handle_message("!list", "!user1") is True
    assert "No posts found." in sender.messages_to("!user1")[0]


def test_list_command_invalid_limit(handler, sender):
    assert handler.handle_message("!list 50", "!user1") is False
    assert "between 1 and 20" in sender.messages_to("!user1")[0]


def test_view_command(handler, sender, db):
    post_id = db.create_post("interesting topic", "!user1", "Alice")
    db.create_comment(post_id, "nice one", "!user2", "Bob")
    assert handler.handle_message(f"!view {post_id}", "!user3") is True
    messages = sender.messages_to("!user3")
    # One merged message: the interface packs it into minimal packets
    assert len(messages) == 1
    assert "interesting topic" in messages[0]
    assert "nice one" in messages[0]
    assert "Alice" in messages[0]


def test_view_missing_post(handler, sender):
    assert handler.handle_message("!view 42", "!user1") is True
    assert "not found" in sender.messages_to("!user1")[0]


def test_post_stores_sender_name(handler, db):
    handler.handle_message("!post found a dog", "!user1", sender_name="Alice's Node")
    assert db.get_post(1)["author_name"] == "Alice's Node"


def test_list_shows_sender_name_instead_of_node_id(handler, sender):
    handler.handle_message("!post found a dog", "!user1", sender_name="Alice's Node")
    handler.handle_message("!list", "!user2")
    listing = sender.messages_to("!user2")[0]
    assert "Alice's Node" in listing
    assert "!user1" not in listing


def test_list_falls_back_to_node_id_without_name(handler, sender):
    handler.handle_message("!post found a dog", "!user1")
    handler.handle_message("!list", "!user2")
    assert "!user1" in sender.messages_to("!user2")[0]


def test_comment_stores_sender_name(handler, db):
    post_id = db.create_post("a post", "!user1")
    handler.handle_message(f"!comment {post_id} me too", "!user2", sender_name="Bob's Node")
    assert db.get_comments_for_post(post_id)[0]["author_name"] == "Bob's Node"


def test_comment_command(handler, sender, db):
    post_id = db.create_post("a post", "!user1")
    assert handler.handle_message(f"!comment {post_id} I agree", "!user2") is True
    comments = db.get_comments_for_post(post_id)
    assert comments[0]["content"] == "I agree"


def test_comment_on_missing_post(handler, sender):
    assert handler.handle_message("!comment 42 hello", "!user1") is True
    assert "not found" in sender.messages_to("!user1")[0]


def test_subscribe_and_notify_on_new_post(handler, sender):
    handler.handle_message("!subscribe all", "!subscriber")
    handler.handle_message("!post breaking news", "!author")

    sub_messages = "\n".join(sender.messages_to("!subscriber"))
    assert "breaking news" in sub_messages


def test_author_not_notified_of_own_post(handler, sender):
    handler.handle_message("!subscribe all", "!author")
    sender.sent.clear()
    handler.handle_message("!post my own post", "!author")

    author_messages = "\n".join(sender.messages_to("!author"))
    assert "New post" not in author_messages


def test_subscribe_post_and_notify_on_comment(handler, sender, db):
    post_id = db.create_post("a post", "!author")
    handler.handle_message(f"!subscribe {post_id}", "!subscriber")
    handler.handle_message(f"!comment {post_id} new comment here", "!commenter")

    sub_messages = "\n".join(sender.messages_to("!subscriber"))
    assert "new comment here" in sub_messages


def test_unsubscribe_all(handler, sender):
    handler.handle_message("!subscribe all", "!user1")
    assert handler.handle_message("!unsubscribe all", "!user1") is True
    assert "unsubscribed from 1" in sender.messages_to("!user1")[-1]


def test_subscriptions_listing(handler, sender, db):
    post_id = db.create_post("a post", "!author")
    handler.handle_message("!subscribe all", "!user1")
    handler.handle_message(f"!subscribe {post_id}", "!user1")
    handler.handle_message("!subscriptions", "!user1")

    combined = "\n".join(sender.messages_to("!user1"))
    assert "All new posts" in combined
    assert f"Post #{post_id}" in combined


def test_info_command(handler, sender, db):
    db.create_post("a post", "!author")
    assert handler.handle_message("!info", "!user1") is True
    combined = "\n".join(sender.messages_to("!user1"))
    assert "Total messages posted: 1" in combined


def test_unknown_broadcast_is_ignored(handler, sender):
    assert handler.handle_message("hello there", "!user1", is_dm=False) is False
    assert sender.sent == []


def test_unknown_dm_gets_help_hint(handler, sender):
    assert handler.handle_message("hello there", "!user1", is_dm=True) is False
    assert "!help" in sender.messages_to("!user1")[0]


def test_unknown_dm_hint_fits_one_packet(handler, sender):
    handler.handle_message("hello there", "!user1", is_dm=True)
    assert len(sender.messages_to("!user1")[0].encode("utf-8")) <= 200


def test_empty_message_is_ignored(handler, sender):
    assert handler.handle_message("   ", "!user1") is False
    assert sender.sent == []


def test_too_long_message_rejected(handler, sender):
    assert handler.handle_message("!post " + "x" * 1100, "!user1") is False
    assert "too long" in sender.messages_to("!user1")[0].lower()


def test_rate_limit(db, sender):
    handler = CommandHandler(database=db, send_message_callback=sender, config={})
    handler.rate_limit_seconds = 60
    assert handler.handle_message("!post first", "!user1") is True
    assert handler.handle_message("!post second", "!user1") is False
    assert db.get_post(2) is None


def test_config_values_used(db, sender):
    config = {
        "Nodeice_board": {
            "Info_URL": "https://example.com/custom",
            "Expiration_Days": 3,
        }
    }
    handler = CommandHandler(database=db, send_message_callback=sender, config=config)
    assert handler.info_url == "https://example.com/custom"
    assert handler.expiration_days == 3
