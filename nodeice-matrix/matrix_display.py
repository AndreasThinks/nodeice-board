#!/usr/bin/env python3
"""
Nodeice Matrix Display - LED Matrix Display for Nodeice Board.

This application displays information from the Nodeice Board on a 32x32 RGB LED matrix,
including the Meshtastic logo, current stats, and new messages.

Usage:
    python matrix_display.py [--config_path=<path>]

Options:
    --config_path=<path>   Path to the configuration file (default: config.yaml)
"""

import os
import sys
import time
import signal
import logging
import argparse
import yaml
import threading
from typing import Dict, Any

from db_monitor import DatabaseMonitor
from display_controller import DisplayController

# Set up logging
def setup_logging(config: Dict[str, Any]):
    """
    Set up logging based on the configuration.
    
    Args:
        config: The configuration dictionary.
    """
    log_config = config.get("logging", {})
    log_level_str = log_config.get("level", "INFO").upper()
    log_file = log_config.get("file", "matrix_display.log")
    
    # Map string log level to logging constants
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    # Create log directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create log directory {log_dir}: {e}")
            log_file = "matrix_display.log"
    
    # Set up logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding='utf-8')
        ]
    )
    
    return logging.getLogger("NodeiceMatrix")

def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.
    
    Args:
        config_path: Path to the configuration file.
        
    Returns:
        The configuration dictionary.
        
    Raises:
        FileNotFoundError: If the configuration file is not found.
        yaml.YAMLError: If the configuration file is invalid.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
        
    return config

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Nodeice Matrix Display - LED Matrix Display for Nodeice Board')
    parser.add_argument('--config_path', default='config.yaml', help='Path to the configuration file')
    
    return parser.parse_args()

class NodeiceMatrixDisplay:
    """Main application class for the Nodeice Matrix Display."""
    
    def __init__(self, config_path: str = 'config.yaml'):
        """
        Initialize the Nodeice Matrix Display application.
        
        Args:
            config_path: Path to the configuration file.
        """
        self.config_path = config_path
        self.config = {}
        self.logger = None
        self.db_monitor = None
        self.display_controller = None
        self.running = False
        
    def initialize(self):
        """Initialize all components of the application."""
        try:
            # Load configuration
            self.config = load_config(self.config_path)
            
            # Set up logging
            self.logger = setup_logging(self.config)
            self.logger.info(f"Nodeice Matrix Display starting up")
            
            # Initialize database monitor
            db_path = self.config["database"]["path"]
            poll_interval = self.config["database"]["poll_interval"]
            self.logger.info(f"Initializing database monitor with path: {db_path}")
            self.db_monitor = DatabaseMonitor(db_path, poll_interval)
            
            # Initialize display controller
            self.logger.info("Initializing display controller")
            self.display_controller = DisplayController(self.config)
            
            # Register callbacks
            self.db_monitor.register_callback(self.display_controller.update)
            
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Initialization error: {e}")
            else:
                print(f"Initialization error: {e}")
            return False
            
    def start(self):
        """Start the Nodeice Matrix Display application."""
        if self.running:
            self.logger.warning("Nodeice Matrix Display is already running")
            return False
            
        try:
            # Start the database monitor
            self.logger.info("Starting database monitor")
            self.db_monitor.start_monitoring()
            
            # Start the display controller in a separate thread
            self.logger.info("Starting display controller")
            self.display_thread = threading.Thread(target=self.display_controller.run)
            self.display_thread.daemon = True
            self.display_thread.start()
            
            self.running = True
            self.logger.info("Nodeice Matrix Display started successfully")
            
            return True
        except Exception as e:
            self.logger.error(f"Error starting Nodeice Matrix Display: {e}")
            self.stop()
            return False
            
    def stop(self):
        """Stop the Nodeice Matrix Display application."""
        self.logger.info("Stopping Nodeice Matrix Display...")
        
        # Stop the database monitor
        if self.db_monitor:
            try:
                self.db_monitor.stop()
            except Exception as e:
                self.logger.error(f"Error stopping database monitor: {e}")
                
        # Stop the display controller
        if self.display_controller:
            try:
                self.display_controller.stop()
            except Exception as e:
                self.logger.error(f"Error stopping display controller: {e}")
                
        self.running = False
        self.logger.info("Nodeice Matrix Display stopped")
            
    def run_forever(self):
        """Run the application until interrupted."""
        if not self.start():
            self.logger.error("Failed to start Nodeice Matrix Display")
            return
            
        # Set up signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            self.logger.info("Interrupt received, shutting down...")
            self.stop()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Keep the main thread alive
        try:
            self.logger.info("Nodeice Matrix Display running, press Ctrl+C to stop")
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            self.stop()

def main():
    """Main entry point for the application."""
    print("Starting Nodeice Matrix Display")
    
    args = parse_args()
    
    app = NodeiceMatrixDisplay(config_path=args.config_path)
    
    if not app.initialize():
        print("Failed to initialize Nodeice Matrix Display")
        sys.exit(1)
        
    app.run_forever()

if __name__ == "__main__":
    main()
