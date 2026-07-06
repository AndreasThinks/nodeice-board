"""Tests for nodeice_board.meshtastic_interface (no hardware required)."""

from unittest.mock import MagicMock

import pytest

from nodeice_board.meshtastic_interface import MeshtasticInterface


def make_interface(on_message=None):
    """Build a MeshtasticInterface with a mocked serial connection."""
    mesh = MeshtasticInterface(on_message=on_message)
    mesh.interface = MagicMock()
    return mesh


class TestSplitLineIntoChunks:
    def test_short_line_unchanged(self):
        assert MeshtasticInterface._split_line_into_chunks("hello", 200) == ["hello"]

    def test_long_line_split_at_word_boundaries(self):
        line = " ".join(["word"] * 100)  # ~500 bytes
        chunks = MeshtasticInterface._split_line_into_chunks(line, 200)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.encode("utf-8")) <= 200
        assert " ".join(chunks) == line  # No content lost

    def test_single_giant_word_hard_split(self):
        line = "x" * 500
        chunks = MeshtasticInterface._split_line_into_chunks(line, 200)
        assert "".join(chunks) == line
        for chunk in chunks:
            assert len(chunk.encode("utf-8")) <= 200

    def test_multibyte_characters_not_split_mid_codepoint(self):
        line = "📌" * 100  # 400 bytes of 4-byte codepoints
        chunks = MeshtasticInterface._split_line_into_chunks(line, 10)
        assert "".join(chunks) == line
        for chunk in chunks:
            encoded = chunk.encode("utf-8")
            assert len(encoded) <= 10
            encoded.decode("utf-8")  # Must be valid UTF-8


class TestSendMessage:
    def test_send_short_message(self):
        mesh = make_interface()
        assert mesh.send_message("hello", "!dest") is True
        mesh.interface.sendText.assert_called_once_with("hello", destinationId="!dest")

    def test_send_broadcast(self):
        mesh = make_interface()
        assert mesh.send_message("hello") is True
        mesh.interface.sendText.assert_called_once_with("hello")

    def test_multiline_message_gets_part_numbers(self):
        mesh = make_interface()
        assert mesh.send_message("line one\nline two", "!dest") is True
        sent = [c.args[0] for c in mesh.interface.sendText.call_args_list]
        assert sent == ["(1/2) line one", "(2/2) line two"]

    def test_long_message_chunked_within_payload_limit(self, monkeypatch):
        monkeypatch.setattr("nodeice_board.meshtastic_interface.time.sleep", lambda s: None)
        mesh = make_interface()
        assert mesh.send_message("word " * 300, "!dest") is True  # ~1500 bytes
        sent = [c.args[0] for c in mesh.interface.sendText.call_args_list]
        assert len(sent) > 1
        for msg in sent:
            assert len(msg.encode("utf-8")) <= 230  # Meshtastic payload limit

    def test_send_fails_when_not_connected(self):
        mesh = MeshtasticInterface()
        assert mesh.send_message("hello", "!dest") is False


class TestOnMessage:
    def test_text_packet_dispatched_to_callback(self):
        received = []
        mesh = make_interface(on_message=lambda msg, sender: received.append((msg, sender)))
        packet = {"id": 1, "decoded": {"text": "!help"}, "fromId": "!node1"}
        mesh.on_message(packet)
        assert received == [("!help", "!node1")]

    def test_duplicate_packet_ignored(self):
        received = []
        mesh = make_interface(on_message=lambda msg, sender: received.append((msg, sender)))
        packet = {"id": 1, "decoded": {"text": "!help"}, "fromId": "!node1"}
        mesh.on_message(packet)
        mesh.on_message(packet)
        assert len(received) == 1

    def test_packet_without_text_ignored(self):
        received = []
        mesh = make_interface(on_message=lambda msg, sender: received.append((msg, sender)))
        mesh.on_message({"id": 2, "decoded": {"portnum": "POSITION_APP"}, "fromId": "!node1"})
        assert received == []

    def test_packet_without_sender_ignored(self):
        received = []
        mesh = make_interface(on_message=lambda msg, sender: received.append((msg, sender)))
        mesh.on_message({"id": 3, "decoded": {"text": "!help"}})
        assert received == []

    def test_bytes_payload_decoded(self):
        received = []
        mesh = make_interface(on_message=lambda msg, sender: received.append((msg, sender)))
        packet = {"id": 4, "decoded": {"payload": "!list".encode("utf-8")}, "fromId": "!node2"}
        mesh.on_message(packet)
        assert received == [("!list", "!node2")]


def test_connection_lost_marks_interface_dead():
    mesh = make_interface()
    serial = mesh.interface
    mesh.on_connection_lost()
    assert mesh.interface is None
    serial.close.assert_called_once()
