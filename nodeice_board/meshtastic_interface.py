import time
import threading
import logging
from typing import Callable, Dict, Any, Optional

import meshtastic
from meshtastic.mesh_interface import MeshInterface
from meshtastic.node import Node
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
        
        # Set up logging
        self.setup_logging()

    def setup_logging(self):
        """Set up logging for the application."""
        self.logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def connect(self) -> bool:
        """
        Connect to the Meshtastic device.
        
        Returns:
            True if connection successful, False otherwise.
        """
        try:
            self.logger.info(f"Connecting to Meshtastic device{' at ' + self.device_path if self.device_path else '...'}")
            self.interface = meshtastic.serial_interface.SerialInterface(devPath=self.device_path)
            
            # Subscribe to receive messages
            pub.subscribe(self.on_message, "meshtastic.receive.data")
            pub.subscribe(self.on_node_updated, "meshtastic.node.updated")
            pub.subscribe(self.on_connection_status, "meshtastic.connection.established")
            
            self.logger.info("Connected to Meshtastic device")
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to Meshtastic device: {e}")
            return False

    def disconnect(self):
        """Disconnect from the Meshtastic device."""
        if self.interface:
            try:
                self.interface.close()
                self.logger.info("Disconnected from Meshtastic device")
            except Exception as e:
                self.logger.error(f"Error disconnecting from Meshtastic device: {e}")
            finally:
                self.interface = None

    def on_connection_status(self, status):
        """
        Called when connection status changes.
        
        Args:
            status: Connection status information.
        """
        self.logger.info(f"Connection status: {status}")

    def on_node_updated(self, node: Node, old_node):
        """
        Called when a node is updated.
        
        Args:
            node: The updated node.
            old_node: The previous state of the node.
        """
        self.logger.info(f"Node updated: {node.id}")

    def on_message(self, packet, sender):
        """
        Called when a message is received.
        
        Args:
            packet: The received packet.
            sender: The sender of the message.
        """
        try:
            if packet.get("decoded", {}).get("portnum") == "TEXT_MESSAGE_APP":
                message = packet.get("decoded", {}).get("text", "")
                sender_id = sender
                
                self.logger.info(f"Message received from {sender_id}: {message}")
                
                # Call the provided callback if available
                if self.on_message_callback:
                    self.on_message_callback(message, sender_id)
        except Exception as e:
            self.logger.error(f"Error processing received message: {e}")

    def send_message(self, message: str, destination: Optional[str] = None) -> bool:
        """
        Send a message to a specific node or broadcast.
        
        Args:
            message: The message to send.
            destination: The destination node ID, or None for broadcast.
            
        Returns:
            True if message sent successfully, False otherwise.
        """
        if not self.interface:
            self.logger.error("Not connected to Meshtastic device")
            return False
        
        try:
            self.logger.info(f"Sending message to {destination if destination else 'all'}: {message}")
            
            # Send message
            if destination:
                # Direct message to specific node
                self.interface.sendText(message, destinationId=destination)
            else:
                # Broadcast message
                self.interface.sendText(message)
                
            return True
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            return False

    def start_background_thread(self):
        """Start a background thread to keep the connection alive."""
        def keep_alive():
            while True:
                time.sleep(30)
                if self.interface:
                    try:
                        # Send a ping or some other lightweight operation
                        self.interface.getNodes()
                    except Exception as e:
                        self.logger.error(f"Error in keep-alive: {e}")
                        # Try to reconnect if needed
                        self.reconnect()
                else:
                    # Try to connect if not connected
                    self.connect()
        
        thread = threading.Thread(target=keep_alive, daemon=True)
        thread.start()
        return thread

    def reconnect(self):
        """Attempt to reconnect to the Meshtastic device."""
        self.disconnect()
        time.sleep(2)  # Wait a bit before reconnecting
        return self.connect()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
