"""Tests for nodeice_board.meshtastic_interface (no hardware required)."""

from unittest.mock import MagicMock

import pytest
from meshtastic.protobuf import portnums_pb2

from nodeice_board.meshtastic_interface import MeshtasticInterface


def make_interface(on_message=None):
    """Build a MeshtasticInterface with a mocked serial connection."""
    mesh = MeshtasticInterface(on_message=on_message)
    mesh.interface = MagicMock()
    mesh.interface.nodes = {}
    mesh.interface.nodesByNum = {}
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


class TestPackMessageIntoChunks:
    def test_short_lines_packed_together(self):
        chunks = MeshtasticInterface._pack_message_into_chunks("one\ntwo\nthree", 200)
        assert chunks == ["one\ntwo\nthree"]

    def test_lines_split_across_chunks_when_full(self):
        lines = [f"line number {i}" for i in range(20)]  # ~280 bytes total
        chunks = MeshtasticInterface._pack_message_into_chunks("\n".join(lines), 100)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.encode("utf-8")) <= 100
        assert "\n".join(chunks).split("\n") == lines  # No content lost or reordered

    def test_overlong_line_still_split(self):
        chunks = MeshtasticInterface._pack_message_into_chunks("x" * 500, 200)
        assert len(chunks) == 3
        assert "".join(chunks) == "x" * 500


class TestSendMessage:
    def test_send_direct_message_requests_ack(self):
        mesh = make_interface()
        assert mesh.send_message("hello", "!dest") is True
        mesh.interface.sendData.assert_called_once_with(
            b"hello",
            destinationId="!dest",
            portNum=portnums_pb2.PortNum.TEXT_MESSAGE_APP,
            wantAck=True,
            onResponse=mesh._on_delivery_response,
            onResponseAckPermitted=True,
        )

    def test_send_broadcast(self):
        mesh = make_interface()
        assert mesh.send_message("hello") is True
        mesh.interface.sendText.assert_called_once_with("hello")

    def test_short_multiline_message_sent_as_one_packet(self):
        mesh = make_interface()
        assert mesh.send_message("line one\nline two", "!dest") is True
        sent = [c.args[0] for c in mesh.interface.sendData.call_args_list]
        assert sent == [b"line one\nline two"]

    def test_long_message_chunked_with_part_numbers(self, monkeypatch):
        monkeypatch.setattr("nodeice_board.meshtastic_interface.time.sleep", lambda s: None)
        mesh = make_interface()
        assert mesh.send_message("word " * 300, "!dest") is True  # ~1500 bytes
        sent = [c.args[0].decode("utf-8") for c in mesh.interface.sendData.call_args_list]
        assert len(sent) > 1
        assert sent[0].startswith(f"(1/{len(sent)}) ")
        for msg in sent:
            assert len(msg.encode("utf-8")) <= 230  # Meshtastic payload limit

    def test_consecutive_sends_are_paced(self, monkeypatch):
        sleeps = []
        monkeypatch.setattr("nodeice_board.meshtastic_interface.time.sleep",
                            lambda s: sleeps.append(s))
        mesh = make_interface()
        mesh.send_message("first", "!dest")
        mesh.send_message("second", "!dest")  # Immediately after
        assert sleeps and max(sleeps) > 1.0  # Second send waited

    def test_send_fails_when_not_connected(self):
        mesh = MeshtasticInterface()
        assert mesh.send_message("hello", "!dest") is False


class TestOnMessage:
    @staticmethod
    def collector():
        received = []
        return received, lambda msg, sender, is_dm, name: received.append(
            (msg, sender, is_dm, name))

    def test_direct_message_dispatched_as_dm(self):
        received, callback = self.collector()
        mesh = make_interface(on_message=callback)
        packet = {"id": 1, "decoded": {"text": "!help"}, "fromId": "!node1", "toId": "!ourboard"}
        mesh.on_message(packet)
        assert received == [("!help", "!node1", True, None)]

    def test_broadcast_dispatched_as_not_dm(self):
        received, callback = self.collector()
        mesh = make_interface(on_message=callback)
        packet = {"id": 1, "decoded": {"text": "hello all"}, "fromId": "!node1", "toId": "^all"}
        mesh.on_message(packet)
        assert received == [("hello all", "!node1", False, None)]

    def test_sender_long_name_resolved_from_node_db(self):
        received, callback = self.collector()
        mesh = make_interface(on_message=callback)
        mesh.interface.nodes = {"!node1": {"user": {"longName": "Alice's Node"}}}
        packet = {"id": 1, "decoded": {"text": "!help"}, "fromId": "!node1", "toId": "!ourboard"}
        mesh.on_message(packet)
        assert received == [("!help", "!node1", True, "Alice's Node")]

    def test_packet_without_to_field_treated_as_broadcast(self):
        received, callback = self.collector()
        mesh = make_interface(on_message=callback)
        mesh.on_message({"id": 1, "decoded": {"text": "!help"}, "fromId": "!node1"})
        assert received == [("!help", "!node1", False, None)]

    def test_duplicate_packet_ignored(self):
        received, callback = self.collector()
        mesh = make_interface(on_message=callback)
        packet = {"id": 1, "decoded": {"text": "!help"}, "fromId": "!node1"}
        mesh.on_message(packet)
        mesh.on_message(packet)
        assert len(received) == 1

    def test_packet_without_text_ignored(self):
        received, callback = self.collector()
        mesh = make_interface(on_message=callback)
        mesh.on_message({"id": 2, "decoded": {"portnum": "POSITION_APP"}, "fromId": "!node1"})
        assert received == []

    def test_packet_without_sender_ignored(self):
        received, callback = self.collector()
        mesh = make_interface(on_message=callback)
        mesh.on_message({"id": 3, "decoded": {"text": "!help"}})
        assert received == []

    def test_bytes_payload_decoded(self):
        received, callback = self.collector()
        mesh = make_interface(on_message=callback)
        packet = {"id": 4, "decoded": {"payload": "!list".encode("utf-8")}, "fromId": "!node2"}
        mesh.on_message(packet)
        assert received == [("!list", "!node2", False, None)]


class TestGetNodeName:
    def test_long_name_preferred(self):
        mesh = make_interface()
        mesh.interface.nodes = {
            "!node1": {"user": {"longName": "Alice's Node", "shortName": "ALCE"}}
        }
        assert mesh.get_node_name("!node1") == "Alice's Node"

    def test_falls_back_to_short_name(self):
        mesh = make_interface()
        mesh.interface.nodes = {"!node1": {"user": {"shortName": "ALCE"}}}
        assert mesh.get_node_name("!node1") == "ALCE"

    def test_unknown_node_returns_none(self):
        mesh = make_interface()
        mesh.interface.nodes = {}
        assert mesh.get_node_name("!stranger") is None

    def test_blank_name_returns_none(self):
        mesh = make_interface()
        mesh.interface.nodes = {"!node1": {"user": {"longName": "  "}}}
        assert mesh.get_node_name("!node1") is None

    def test_numeric_id_resolved_via_nodes_by_num(self):
        mesh = make_interface()
        mesh.interface.nodes = {}
        mesh.interface.nodesByNum = {123456: {"user": {"longName": "Bob's Node"}}}
        assert mesh.get_node_name("123456") == "Bob's Node"

    def test_not_connected_returns_none(self):
        mesh = MeshtasticInterface()
        assert mesh.get_node_name("!node1") is None


def test_connection_lost_marks_interface_dead():
    mesh = make_interface()
    serial = mesh.interface
    mesh.on_connection_lost()
    assert mesh.interface is None
    serial.close.assert_called_once()
