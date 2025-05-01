#!/usr/bin/env python3
"""
Nodeice Board - A Meshtastic-based notice board application.

This application allows Meshtastic users to post messages and comments
to a central notice board node. Messages older than 7 days are automatically
deleted.

Usage:
    python main.py [--device_path=<path>] [--db_path=<path>]

Options:
    --device_path=<path>   Path to the Meshtastic device (optional, auto-detects if not provided)
    --db_path=<path>       Path to the database file (default: nodeice_board.db)
"""

import os
import sys
import time
import signal
import logging
import argparse
from typing import Optional

from nodeice_board.database import Database
from nodeice_board.meshtastic_interface import MeshtasticInterface
from nodeice_board.command_handler import CommandHandler
from nodeice_board.post_expiration import PostExpirationHandler


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('nodeice_board.log')
    ]
)
logger = logging.getLogger("NodeiceBoard")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Nodeice Board - Meshtastic notice board application')
    parser.add_argument('--device_path', help='Path to the Meshtastic device (optional, auto-detects if not provided)')
    parser.add_argument('--db_path', default='nodeice_board.db', help='Path to the database file')
    return parser.parse_args()


class NodeiceBoard:
    """Main application class for the Nodeice Board."""
    
    def __init__(self, device_path: Optional[str] = None, db_path: str = 'nodeice_board.db'):
        """
        Initialize the Nodeice Board application.
        
        Args:
            device_path: Path to the Meshtastic device. If None, auto-detect.
            db_path: Path to the SQLite database file.
        """
        self.device_path = device_path
        self.db_path = db_path
        self.db = None
        self.mesh_interface = None
        self.command_handler = None
        self.expiration_handler = None
        self.running = False
        
    def initialize(self):
        """Initialize all components of the application."""
        try:
            # Initialize database
            logger.info(f"Initializing database at {self.db_path}")
            self.db = Database(self.db_path)
            
            # Initialize Meshtastic interface
            logger.info("Initializing Meshtastic interface")
            self.mesh_interface = MeshtasticInterface(
                device_path=self.device_path, 
                on_message=self.on_message_received
            )
            
            # Initialize command handler
            logger.info("Initializing command handler")
            self.command_handler = CommandHandler(
                database=self.db,
                send_message_callback=self.mesh_interface.send_message
            )
            
            # Initialize post expiration handler
            logger.info("Initializing post expiration handler")
            self.expiration_handler = PostExpirationHandler(
                database=self.db,
                expiration_days=7,  # Posts expire after 7 days
                check_interval_hours=6  # Check for expired posts every 6 hours
            )
            
            return True
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            return False
            
    def start(self):
        """Start the Nodeice Board application."""
        if self.running:
            logger.warning("Nodeice Board is already running")
            return False
            
        try:
            # Connect to Meshtastic device
            if not self.mesh_interface.connect():
                logger.error("Failed to connect to Meshtastic device")
                return False
                
            # Start the keep-alive thread
            self.mesh_interface.start_background_thread()
            
            # Start the post expiration handler
            self.expiration_handler.start()
            
            self.running = True
            logger.info("Nodeice Board started successfully")
            
            # Send a broadcast message to announce the board is online
            self.mesh_interface.send_message(
                "Nodeice Board is now online! Send !help for available commands."
            )
            
            return True
        except Exception as e:
            logger.error(f"Error starting Nodeice Board: {e}")
            self.stop()
            return False
            
    def stop(self):
        """Stop the Nodeice Board application."""
        logger.info("Stopping Nodeice Board...")
        
        # Stop the expiration handler
        if self.expiration_handler:
            try:
                self.expiration_handler.stop()
            except Exception as e:
                logger.error(f"Error stopping expiration handler: {e}")
                
        # Disconnect from Meshtastic device
        if self.mesh_interface:
            try:
                self.mesh_interface.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting from Meshtastic: {e}")
                
        # Close database connection
        if self.db:
            try:
                self.db.close()
            except Exception as e:
                logger.error(f"Error closing database: {e}")
                
        self.running = False
        logger.info("Nodeice Board stopped")
            
    def on_message_received(self, message: str, sender_id: str):
        """
        Handle received Meshtastic messages.
        
        Args:
            message: The received message content.
            sender_id: The ID of the sender.
        """
        logger.info(f"Processing message from {sender_id}: {message}")
        
        if self.command_handler:
            self.command_handler.handle_message(message, sender_id)
        else:
            logger.error("Command handler not initialized")
            
    def run_forever(self):
        """Run the application until interrupted."""
        if not self.start():
            logger.error("Failed to start Nodeice Board")
            return
            
        # Set up signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Interrupt received, shutting down...")
            self.stop()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep the main thread alive
        try:
            logger.info("Nodeice Board running, press Ctrl+C to stop")
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()


def main():
    """Main entry point for the application."""
    print("Starting Nodeice Board - Meshtastic Notice Board Application")
    
    args = parse_args()
    
    app = NodeiceBoard(
        device_path=args.device_path,
        db_path=args.db_path
    )
    
    if not app.initialize():
        logger.error("Failed to initialize Nodeice Board")
        sys.exit(1)
        
    app.run_forever()


if __name__ == "__main__":
    main()
