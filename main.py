#!/usr/bin/env python3
"""
Nodeice Board - A Meshtastic-based notice board application.

This application allows Meshtastic users to post messages and comments
to a central notice board node. Users can subscribe to receive notifications
about new posts or when specific posts receive comments. Messages older than 
the configured expiration period (default: 7 days) are automatically deleted.

Security features:
- Input validation and sanitization to prevent SQL injection
- Rate limiting to prevent abuse
- Connection timeout and retry logic for database operations
- Parameter validation for all database operations

Usage:
    python main.py [--device_path=<path>] [--db_path=<path>] [--config_path=<path>]

Options:
    --device_path=<path>   Path to the Meshtastic device (optional, auto-detects if not provided)
    --db_path=<path>       Path to the database file (default: nodeice_board.db)
    --config_path=<path>   Path to the configuration file (default: config.yaml)
"""

import os
import sys
import time
import signal
import logging
import argparse
import traceback
from typing import Optional
import re

from nodeice_board.database import Database
from nodeice_board.meshtastic_interface import MeshtasticInterface
from nodeice_board.command_handler import CommandHandler
from nodeice_board.post_expiration import PostExpirationHandler
from nodeice_board.metrics_collector import MetricsCollector
from nodeice_board.config import load_config, get_device_names, get_expiration_days


# Set up logging
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG level to see detailed encoding information
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('nodeice_board.log', encoding='utf-8')  # Explicit UTF-8 encoding for log file
    ]
)
logger = logging.getLogger("NodeiceBoard")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Nodeice Board - Meshtastic notice board application')
    parser.add_argument('--device_path', help='Path to the Meshtastic device (optional, auto-detects if not provided)')
    parser.add_argument('--db_path', default='nodeice_board.db', help='Path to the database file')
    parser.add_argument('--config_path', default='config.yaml', help='Path to the configuration file')
    
    args = parser.parse_args()
    
    # Validate paths to prevent path traversal attacks
    for path_arg in [args.db_path, args.config_path]:
        if path_arg and not is_safe_path(path_arg):
            parser.error(f"Unsafe path: {path_arg}")
    
    return args

def is_safe_path(path: str) -> bool:
    """
    Check if a path is safe (no directory traversal).
    
    Args:
        path: The path to check.
        
    Returns:
        True if the path is safe, False otherwise.
    """
    # Check for common directory traversal patterns
    if re.search(r'\.\./', path) or re.search(r'\.\.\\', path):
        return False
        
    # Normalize path to catch more complex traversal attempts
    norm_path = os.path.normpath(path)
    if '..' in norm_path.split(os.sep):
        return False
        
    return True


class NodeiceBoard:
    """Main application class for the Nodeice Board."""
    
    def __init__(self, device_path: Optional[str] = None, db_path: str = 'nodeice_board.db', config_path: str = 'config.yaml'):
        """
        Initialize the Nodeice Board application.
        
        Args:
            device_path: Path to the Meshtastic device. If None, auto-detect.
            db_path: Path to the SQLite database file.
            config_path: Path to the configuration file.
            
        Raises:
            ValueError: If paths are invalid.
        """
        # Validate paths
        if not is_safe_path(db_path):
            raise ValueError(f"Unsafe database path: {db_path}")
            
        if not is_safe_path(config_path):
            raise ValueError(f"Unsafe config path: {config_path}")
        self.device_path = device_path
        self.db_path = db_path
        self.config_path = config_path
        self.config = {}
        self.db = None
        self.mesh_interface = None
        self.command_handler = None
        self.expiration_handler = None
        self.metrics_collector = None
        self.running = False
        
        # Load configuration
        self.load_config()
        
    def load_config(self):
        """Load configuration from the config file."""
        logger.info(f"Loading configuration from {self.config_path}")
        self.config = load_config(self.config_path)
        
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
            expiration_days = get_expiration_days(self.config)
            self.expiration_handler = PostExpirationHandler(
                database=self.db,
                expiration_days=expiration_days,  # Posts expire after configured number of days
                check_interval_hours=6  # Check for expired posts every 6 hours
            )
            
            # Initialize metrics collector
            logger.info("Initializing metrics collector")
            self.metrics_collector = MetricsCollector(
                database=self.db,
                mesh_interface=self.mesh_interface,
                collection_interval_seconds=300  # Collect metrics every 5 minutes
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
            # Get device names from config
            long_name, short_name = get_device_names(self.config)
            if long_name or short_name:
                logger.info(f"Using device names from config: long_name='{long_name}', short_name='{short_name}'")
            
            # Connect to Meshtastic device
            if not self.mesh_interface.connect(long_name=long_name, short_name=short_name):
                logger.error("Failed to connect to Meshtastic device")
                return False
                
            # Start the keep-alive thread
            self.mesh_interface.start_background_thread()
            
            # Start the post expiration handler
            self.expiration_handler.start()
            
            # Start the metrics collector
            self.metrics_collector.start()
            
            self.running = True
            logger.info("Nodeice Board started successfully")
            
            # Don't send a broadcast message - wait for users to message first
            # This prevents spamming the network with announcements
            
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
                
        # Stop the metrics collector
        if self.metrics_collector:
            try:
                self.metrics_collector.stop()
            except Exception as e:
                logger.error(f"Error stopping metrics collector: {e}")
                
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
        try:
            logger.info(f"NodeiceBoard.on_message_received called with message from {sender_id}: {message}")
            
            # Basic input validation
            if not message:
                logger.warning(f"Received empty message from {sender_id}")
                return
                
            # Limit message size to prevent DoS
            if len(message) > 2000:  # Reasonable limit for Meshtastic messages
                logger.warning(f"Message too long from {sender_id}: {len(message)} chars")
                if self.mesh_interface:
                    self.mesh_interface.send_message(
                        "Message too long. Please keep messages under 2000 characters.",
                        sender_id
                    )
                return
                
            if self.command_handler:
                # Log the command being processed
                if message.startswith('!'):
                    command_parts = message.split()
                    command = command_parts[0] if command_parts else message
                    logger.info(f"Received command: {command} from {sender_id}")
                
                # Handle the message
                logger.debug(f"Passing message to command_handler.handle_message: '{message}'")
                result = self.command_handler.handle_message(message, sender_id)
                logger.info(f"Command handling result: {'Success' if result else 'Failed'}")
            else:
                logger.error("Command handler not initialized")
        except Exception as e:
            logger.error(f"Error in message handler: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
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
    
    # Kill any previous instances to avoid conflicts
    import subprocess
    import os
    
    kill_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kill_previous_instances.sh")
    try:
        print("Checking for previous instances...")
        # Make the script executable if it's not already
        subprocess.run(["chmod", "+x", kill_script], check=False)
        # Run the script to kill any previous instances
        subprocess.run(["bash", kill_script], check=False)
        print("Previous instance check completed.")
    except Exception as e:
        print(f"Warning: Failed to check for previous instances: {e}")
    
    args = parse_args()
    
    app = NodeiceBoard(
        device_path=args.device_path,
        db_path=args.db_path,
        config_path=args.config_path
    )
    
    if not app.initialize():
        logger.error("Failed to initialize Nodeice Board")
        sys.exit(1)
        
    app.run_forever()


if __name__ == "__main__":
    main()
