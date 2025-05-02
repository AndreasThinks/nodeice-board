import time
import threading
import logging
import traceback
from typing import Callable, Dict, Any, Optional

from meshtastic.serial_interface import SerialInterface

import meshtastic
from pubsub import pub


class MeshtasticInterface:
    """Interface for communicating with Meshtastic devices."""

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
        
        # Set up logging
        self.setup_logging()
        
        # Keep track of processed messages to avoid duplicates
        self.processed_messages = set()
        self.processed_messages_lock = threading.Lock()

    def setup_logging(self):
        """Set up logging for the application."""
        self.logger.setLevel(logging.DEBUG)  # Set to DEBUG to see detailed encoding information
        
        # Stream handler for console output
        stream_handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(formatter)
        self.logger.addHandler(stream_handler)
        
        # File handler with explicit UTF-8 encoding
        try:
            file_handler = logging.FileHandler('meshtastic_interface.log', encoding='utf-8')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
        except Exception as e:
            self.logger.warning(f"Could not create file handler: {e}")

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
            
            # Use the updated Meshtastic API
            if self.device_path:
                self.interface = SerialInterface(self.device_path)
            else:
                self.interface = SerialInterface()
            
            # Subscribe to receive messages
            # Subscribe to multiple potential topics to ensure we catch all messages
            pub.subscribe(self.on_message, "meshtastic.receive.text")
            pub.subscribe(self.on_message, "meshtastic.receive.data")
            pub.subscribe(self.on_message, "meshtastic.receive")
            
            # Set device names if provided
            if long_name or short_name:
                self.set_device_name(long_name, short_name)
            
            self.logger.info("Connected to Meshtastic device")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Meshtastic device: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def disconnect(self):
        """Disconnect from the Meshtastic device."""
        if self.interface:
            try:
                # Unsubscribe from all pubsub topics
                try:
                    pub.unsubscribe(self.on_message, "meshtastic.receive.text")
                    pub.unsubscribe(self.on_message, "meshtastic.receive.data")
                    pub.unsubscribe(self.on_message, "meshtastic.receive")
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
            
            self.logger.info(f"Message received from {from_id}: {message}")
            
            # Call the provided callback if available
            if self.on_message_callback:
                self.logger.debug(f"Calling on_message_callback with message: '{message}' from {from_id}")
                try:
                    # Use the main thread to call the callback to avoid thread issues
                    self.on_message_callback(message, from_id)
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

    def send_message(self, message: str, destination: Optional[str] = None) -> bool:
        """
        Send a message to a specific node or broadcast.
        Break up large messages into smaller chunks to avoid TOO_LARGE errors.
        
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
            
            # Split the message into lines
            lines = message.strip().split('\n')
            success = True
            
            # Send each line as a separate message
            for i, line in enumerate(lines):
                if not line.strip():
                    continue  # Skip empty lines
                
                # Add line number prefix if there are multiple lines
                if len(lines) > 1:
                    line_msg = f"({i+1}/{len(lines)}) {line}"
                else:
                    line_msg = line
                
                self.logger.debug(f"Sending message part {i+1}/{len(lines)}: {line_msg}")
                
                try:
                    # Send message using the current Meshtastic API
                    if destination:
                        # Direct message to specific node
                        self.interface.sendText(line_msg, destinationId=destination)
                    else:
                        # Broadcast message
                        self.interface.sendText(line_msg)
                    
                    # Add a small delay between messages to avoid flooding the network
                    if i < len(lines) - 1:
                        time.sleep(0.5)
                        
                except Exception as line_error:
                    self.logger.error(f"Failed to send message part {i+1}/{len(lines)}: {line_error}")
                    success = False
            
            return success
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def start_background_thread(self):
        """Start a background thread to keep the connection alive."""
        def keep_alive():
            reconnect_attempts = 0
            max_reconnect_attempts = 5
            reconnect_delay = 30  # seconds
            
            while True:
                time.sleep(30)
                if self.interface:
                    try:
                        # Simple ping to check if the connection is still alive
                        self.logger.debug("Checking connection status")
                        # We don't use getNodes() or sendHeartbeat() as they might not be available
                        # in all versions of the Meshtastic library
                        reconnect_attempts = 0  # Reset counter on successful check
                    except Exception as e:
                        self.logger.error(f"Error in keep-alive: {e}")
                        self.logger.error(f"Traceback: {traceback.format_exc()}")
                        
                        # Limit reconnection attempts to avoid spamming
                        reconnect_attempts += 1
                        if reconnect_attempts <= max_reconnect_attempts:
                            self.logger.info(f"Attempting to reconnect (attempt {reconnect_attempts}/{max_reconnect_attempts})")
                            # Try to reconnect if needed
                            self.reconnect(long_name=self.long_name, short_name=self.short_name)
                        else:
                            self.logger.warning(f"Max reconnection attempts reached. Waiting {reconnect_delay} seconds before trying again.")
                            time.sleep(reconnect_delay)
                            reconnect_attempts = 0
                else:
                    # Try to connect if not connected
                    self.connect(long_name=self.long_name, short_name=self.short_name)
        
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
            
            # Log the encoding details to help diagnose issues
            if long_name:
                self.logger.debug(f"Long name encoding details: {repr(long_name)}, length: {len(long_name)}")
            if short_name:
                self.logger.debug(f"Short name encoding details: {repr(short_name)}, length: {len(short_name)}")
            
            # Check if localNode is available
            if not hasattr(self.interface, 'localNode'):
                self.logger.error("Interface does not have localNode attribute")
                return False
                
            # Set the owner information using the localNode
            if long_name is not None or short_name is not None:
                try:
                    # Use the example from the Meshtastic library
                    self.logger.debug("Calling localNode.setOwner with Unicode strings")
                    self.interface.localNode.setOwner(long_name, short_name)
                    self.logger.info("Device name updated successfully")
                except Exception as e:
                    self.logger.error(f"Error in setOwner: {e}")
                    # Try with explicit encoding if there was an error
                    try:
                        self.logger.debug("Trying alternative approach with explicit encoding")
                        # If the first attempt failed, try ensuring the strings are properly encoded
                        if long_name:
                            long_name = long_name.encode('utf-8').decode('utf-8')
                        if short_name:
                            short_name = short_name.encode('utf-8').decode('utf-8')
                        self.interface.localNode.setOwner(long_name, short_name)
                        self.logger.info("Device name updated successfully with explicit encoding")
                    except Exception as e2:
                        self.logger.error(f"Error in second setOwner attempt: {e2}")
                        return False
                
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
