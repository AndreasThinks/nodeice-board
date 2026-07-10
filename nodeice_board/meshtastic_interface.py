import time
import threading
import logging
import traceback
from typing import Callable, Dict, Any, List, Optional

from meshtastic.serial_interface import SerialInterface

import meshtastic
from meshtastic.protobuf import portnums_pb2
from pubsub import pub


class MeshtasticInterface:
    """Interface for communicating with Meshtastic devices."""

    # Meshtastic text payloads max out around 230 bytes; leave headroom for
    # the "(i/n) " chunk prefix added to multi-part messages.
    MAX_PAYLOAD_BYTES = 200

    # Minimum gap between our transmissions. A LongFast packet needs 1-2s
    # of airtime plus the ACK round-trip; sending sooner risks colliding
    # with the recipient's ACK for the previous packet.
    MIN_SEND_INTERVAL_S = 2.0

    def __init__(self, device_path: Optional[str] = None, on_message: Optional[Callable] = None):
        """
        Initialize the Meshtastic interface.

        Args:
            device_path: Path to the Meshtastic device. If None, auto-detect.
            on_message: Callback function to be called when a message is received.
        """
        self.device_path = device_path
        self.interface = None
        self.on_message_callback = on_message
        self.logger = logging.getLogger("NodeiceBoard")

        # Device name settings
        self.long_name = None
        self.short_name = None

        # Keep track of processed messages to avoid duplicates
        self.processed_messages = set()
        self.processed_messages_lock = threading.Lock()

        # When we last transmitted, for pacing consecutive sends
        self._last_send_time = 0.0

    def connect(self, long_name: Optional[str] = None, short_name: Optional[str] = None) -> bool:
        """
        Connect to the Meshtastic device and optionally set device names.

        Args:
            long_name: Long name to set for the device (optional)
            short_name: Short name to set for the device (optional)

        Returns:
            True if connection successful, False otherwise.
        """
        # Store the device names for reconnection
        self.long_name = long_name
        self.short_name = short_name

        try:
            self.logger.info(f"Connecting to Meshtastic device{' at ' + self.device_path if self.device_path else '...'}")

            if self.device_path:
                self.interface = SerialInterface(self.device_path)
            else:
                self.interface = SerialInterface()

            # Subscribe to incoming text messages. Subscribing to both the
            # "meshtastic.receive.text" topic and its parent would deliver each
            # message multiple times, so use only the text topic.
            pub.subscribe(self.on_message, "meshtastic.receive.text")

            # Get notified when the serial connection drops so the keep-alive
            # thread can reconnect.
            pub.subscribe(self.on_connection_lost, "meshtastic.connection.lost")

            # Set device names if provided
            if long_name or short_name:
                self.set_device_name(long_name, short_name)

            self.logger.info("Connected to Meshtastic device")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Meshtastic device: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.interface = None
            return False

    def disconnect(self):
        """Disconnect from the Meshtastic device."""
        if self.interface:
            try:
                # Unsubscribe from all pubsub topics
                try:
                    pub.unsubscribe(self.on_message, "meshtastic.receive.text")
                    pub.unsubscribe(self.on_connection_lost, "meshtastic.connection.lost")
                    self.logger.debug("Unsubscribed from all pubsub topics")
                except Exception as unsub_error:
                    self.logger.warning(f"Error unsubscribing from pubsub topics: {unsub_error}")

                self.interface.close()
                self.logger.info("Disconnected from Meshtastic device")
            except Exception as e:
                self.logger.error(f"Error disconnecting from Meshtastic device: {e}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
            finally:
                self.interface = None

    def on_connection_lost(self, interface=None, **kwargs):
        """
        Called by the Meshtastic library when the serial connection drops.

        Marks the interface as disconnected; the keep-alive thread notices
        and attempts to reconnect.
        """
        self.logger.warning("Connection to Meshtastic device lost; will attempt to reconnect")
        try:
            if self.interface:
                self.interface.close()
        except Exception:
            pass
        self.interface = None

    def on_message(self, packet, interface=None, **kwargs):
        """
        Called when a message is received.

        Args:
            packet: The received packet.
            interface: The interface that received the message (provided by Meshtastic).
            **kwargs: Additional arguments provided by pubsub.
        """
        try:
            self.logger.debug(f"on_message called with packet: {packet}")

            # Extract message ID if available
            message_id = None
            if "id" in packet:
                message_id = packet["id"]

            # Extract message text - handle different packet formats
            message = None

            # Try to extract message from decoded.text (common format)
            if "decoded" in packet and isinstance(packet["decoded"], dict):
                if "text" in packet["decoded"]:
                    message = packet["decoded"]["text"]
                elif "payload" in packet["decoded"] and packet["decoded"]["payload"]:
                    # Try to decode payload as text if present
                    try:
                        if isinstance(packet["decoded"]["payload"], bytes):
                            message = packet["decoded"]["payload"].decode('utf-8')
                        elif isinstance(packet["decoded"]["payload"], str):
                            message = packet["decoded"]["payload"]
                    except Exception as decode_error:
                        self.logger.warning(f"Failed to decode payload: {decode_error}")

            # If we still don't have a message, check for other possible locations
            if not message and "text" in packet:
                message = packet["text"]

            if not message:
                self.logger.debug(f"Could not extract message text from packet: {packet}")
                return

            # Get sender information - handle different packet formats
            from_id = None

            # Try different possible field names for sender ID
            for field in ["fromId", "from", "sender", "source", "src"]:
                if field in packet and packet[field]:
                    from_id = str(packet[field])
                    break

            if not from_id:
                self.logger.warning(f"Received message without sender ID: {message}")
                return

            # A text is a direct message when addressed to a specific node
            # rather than the broadcast address (channel chatter)
            to_id = packet.get("toId", packet.get("to"))
            is_dm = to_id not in (None, meshtastic.BROADCAST_ADDR, meshtastic.BROADCAST_NUM)

            # Create a unique identifier for this message
            if message_id:
                message_key = f"{message_id}"
            else:
                # If no message ID, use a combination of sender, message, and timestamp
                message_key = f"{from_id}:{message}:{time.time():.0f}"

            # Check if we've already processed this message
            with self.processed_messages_lock:
                if message_key in self.processed_messages:
                    self.logger.debug(f"Skipping duplicate message: {message_key}")
                    return

                # Add to processed messages
                self.processed_messages.add(message_key)

                # Limit the size of the processed messages set
                if len(self.processed_messages) > 100:
                    # Remove oldest entries (assuming they're added in order)
                    self.processed_messages = set(list(self.processed_messages)[-100:])

            self.logger.info(f"Message received from {from_id} ({'DM' if is_dm else 'broadcast'}): {message}")

            # Call the provided callback if available
            if self.on_message_callback:
                self.logger.debug(f"Calling on_message_callback with message: '{message}' from {from_id}")
                try:
                    self.on_message_callback(message, from_id, is_dm)
                    self.logger.debug(f"on_message_callback completed successfully for message: '{message}'")
                except Exception as callback_error:
                    self.logger.error(f"Error in on_message_callback: {callback_error}")
                    self.logger.error(f"Traceback: {traceback.format_exc()}")
            else:
                self.logger.warning("Received message but no callback is registered to handle it")
        except Exception as e:
            self.logger.error(f"Error processing received message: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.logger.error(f"Packet data: {packet}")

    @classmethod
    def _split_line_into_chunks(cls, line: str, max_bytes: int) -> List[str]:
        """
        Split a line into chunks that each fit within max_bytes of UTF-8,
        preferring to break at word boundaries.

        Args:
            line: The text to split.
            max_bytes: Maximum UTF-8 encoded size of each chunk.

        Returns:
            A list of chunks (never empty for non-empty input).
        """
        if len(line.encode('utf-8')) <= max_bytes:
            return [line]

        chunks = []
        current = ""
        for word in line.split(' '):
            candidate = f"{current} {word}" if current else word
            if len(candidate.encode('utf-8')) <= max_bytes:
                current = candidate
                continue

            if current:
                chunks.append(current)
                current = ""

            # A single word longer than max_bytes: hard-split by characters
            piece = ""
            for ch in word:
                if len((piece + ch).encode('utf-8')) > max_bytes:
                    chunks.append(piece)
                    piece = ch
                else:
                    piece += ch
            current = piece

        if current:
            chunks.append(current)
        return chunks

    @classmethod
    def _pack_message_into_chunks(cls, message: str, max_bytes: int) -> List[str]:
        """
        Pack a message into as few chunks as possible: overlong lines are
        split at word boundaries, then consecutive lines are packed back
        together (newline-separated) while they fit within max_bytes.
        Fewer chunks means fewer LoRa packets on the air.

        Args:
            message: The full message text.
            max_bytes: Maximum UTF-8 encoded size of each chunk.

        Returns:
            A list of chunks (empty for whitespace-only input).
        """
        pieces = []
        for line in message.strip().split('\n'):
            if not line.strip():
                continue  # Skip empty lines
            pieces.extend(cls._split_line_into_chunks(line, max_bytes))

        chunks = []
        current = ""
        for piece in pieces:
            candidate = f"{current}\n{piece}" if current else piece
            if len(candidate.encode('utf-8')) <= max_bytes:
                current = candidate
            else:
                chunks.append(current)
                current = piece
        if current:
            chunks.append(current)
        return chunks

    def _pace_transmission(self):
        """Sleep as needed so consecutive sends stay MIN_SEND_INTERVAL_S apart."""
        wait = self._last_send_time + self.MIN_SEND_INTERVAL_S - time.monotonic()
        if wait > 0:
            time.sleep(wait)

    def _on_delivery_response(self, packet):
        """
        Log the routing ACK/NAK the mesh returns for an ACK-requested DM.

        The confirmation may come from the destination itself or, as an
        implicit ACK, from a node that relayed the packet onward.
        """
        try:
            routing = packet.get("decoded", {}).get("routing", {})
            error = routing.get("errorReason", "NONE")
            origin = packet.get("fromId", packet.get("from", "?"))
            if error == "NONE":
                self.logger.info(f"Delivery confirmed by {origin}")
            else:
                self.logger.warning(f"Delivery failed ({error}) reported by {origin}")
        except Exception as e:
            self.logger.debug(f"Could not parse delivery response: {e}")

    def send_message(self, message: str, destination: Optional[str] = None) -> bool:
        """
        Send a message to a specific node or broadcast.
        Breaks up large messages into chunks that fit within the Meshtastic
        payload limit to avoid TOO_LARGE errors.

        Args:
            message: The message to send.
            destination: The destination node ID, or None for broadcast.

        Returns:
            True if all message chunks were sent successfully, False otherwise.
        """
        if not self.interface:
            self.logger.error("Not connected to Meshtastic device")
            return False

        try:
            self.logger.info(f"MeshtasticInterface.send_message called with message to {destination if destination else 'all'}: {message}")

            # Pack the message into as few payload-sized chunks as possible
            chunks = self._pack_message_into_chunks(message, self.MAX_PAYLOAD_BYTES)

            if not chunks:
                return True  # Nothing to send

            success = True
            for i, chunk in enumerate(chunks):
                # Add a part-number prefix if there are multiple chunks
                if len(chunks) > 1:
                    chunk_msg = f"({i+1}/{len(chunks)}) {chunk}"
                else:
                    chunk_msg = chunk

                self.logger.debug(f"Sending message part {i+1}/{len(chunks)}: {chunk_msg}")

                try:
                    self._pace_transmission()
                    if destination:
                        # Direct message: request an ACK so the radio
                        # retransmits chunks that get lost on the air.
                        # sendData rather than sendText because only it
                        # exposes onResponseAckPermitted, without which the
                        # delivery callback fires for errors but not ACKs.
                        self.interface.sendData(
                            chunk_msg.encode("utf-8"),
                            destinationId=destination,
                            portNum=portnums_pb2.PortNum.TEXT_MESSAGE_APP,
                            wantAck=True,
                            onResponse=self._on_delivery_response,
                            onResponseAckPermitted=True,
                        )
                    else:
                        # Broadcast message
                        self.interface.sendText(chunk_msg)
                    self._last_send_time = time.monotonic()

                except Exception as chunk_error:
                    self.logger.error(f"Failed to send message part {i+1}/{len(chunks)}: {chunk_error}")
                    success = False

            return success
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def start_background_thread(self):
        """Start a background thread that reconnects if the connection drops."""
        def keep_alive():
            while True:
                time.sleep(30)
                if self.interface is None:
                    self.logger.info("Not connected; attempting to reconnect to Meshtastic device")
                    try:
                        self.connect(long_name=self.long_name, short_name=self.short_name)
                    except Exception as e:
                        self.logger.error(f"Reconnect attempt failed: {e}")

        thread = threading.Thread(target=keep_alive, daemon=True)
        thread.start()
        return thread

    def set_device_name(self, long_name: Optional[str] = None, short_name: Optional[str] = None) -> bool:
        """
        Set the device name.

        Args:
            long_name: Long name to set for the device (optional)
            short_name: Short name to set for the device (optional)

        Returns:
            True if successful, False otherwise.
        """
        if not self.interface:
            self.logger.error("Not connected to Meshtastic device")
            return False

        try:
            self.logger.info(f"Setting device name: long_name='{long_name}', short_name='{short_name}'")

            # Check if localNode is available
            if not hasattr(self.interface, 'localNode'):
                self.logger.error("Interface does not have localNode attribute")
                return False

            # Set the owner information using the localNode
            if long_name is not None or short_name is not None:
                self.interface.localNode.setOwner(long_name, short_name)
                self.logger.info("Device name updated successfully")

            return True
        except Exception as e:
            self.logger.error(f"Failed to set device name: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def reconnect(self, long_name: Optional[str] = None, short_name: Optional[str] = None):
        """
        Attempt to reconnect to the Meshtastic device.

        Args:
            long_name: Long name to set for the device (optional)
            short_name: Short name to set for the device (optional)

        Returns:
            True if reconnection successful, False otherwise.
        """
        self.disconnect()
        time.sleep(2)  # Wait a bit before reconnecting
        return self.connect(long_name=long_name, short_name=short_name)

    def __enter__(self):
        """Context manager entry."""
        self.connect(long_name=self.long_name, short_name=self.short_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
