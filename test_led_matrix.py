#!/usr/bin/env python3
"""
Test script for the RGB LED Matrix display.

This script tests various display functions and effects of the LED matrix display
for the Nodeice Board application.

Usage:
    python test_led_matrix.py [--config=<path>] [--test=<test_name>]

Options:
    --config=<path>    Path to the configuration file (default: config.yaml)
    --test=<test_name> Test to run: all, logo, text, status, message (default: all)
"""

import os
import sys
import time
import argparse
import logging
from PIL import Image

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("LEDMatrixTest")

# Try to import the required modules
try:
    from nodeice_board.led_matrix_display import LEDMatrixDisplay, RGBMATRIX_AVAILABLE
    from nodeice_board.config import load_config, get_led_matrix_config
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error("Make sure you're running this script from the project root directory")
    sys.exit(1)

class MockDatabase:
    """Mock database class for testing the LED matrix display."""
    
    def __init__(self):
        """Initialize the mock database."""
        self.total_posts = 42
        self.connected_nodes = 5
        self.discovered_nodes = 8
        
    def get_total_posts_count(self):
        """Get the total number of posts."""
        return self.total_posts

def test_logo_display(matrix):
    """Test displaying the logo."""
    logger.info("Testing logo display...")
    
    # The logo is already displayed in the status display
    # Just wait for a few seconds to observe it
    for i in range(5):
        logger.info(f"Logo display test: {i+1}/5 seconds")
        time.sleep(1)
    
    logger.info("Logo display test completed")
    return True

def test_text_display(matrix):
    """Test displaying text."""
    logger.info("Testing text display...")
    
    # Display a test message with the rainbow effect
    matrix.display_message("Test message with rainbow effect", "TEST001", "rainbow")
    time.sleep(5)
    
    logger.info("Text display test completed")
    return True

def test_status_cycle(matrix):
    """Test the status display cycle."""
    logger.info("Testing status cycle...")
    
    # The status cycle runs automatically in the background
    # Just wait for a full cycle to observe all status screens
    cycle_seconds = matrix.status_cycle_seconds
    total_wait = cycle_seconds * 5  # 5 different status screens
    
    logger.info(f"Waiting for a full status cycle ({total_wait} seconds)...")
    for i in range(total_wait):
        if i % cycle_seconds == 0:
            logger.info(f"Status screen {(i // cycle_seconds) + 1}/5")
        time.sleep(1)
    
    logger.info("Status cycle test completed")
    return True

def test_message_effects(matrix):
    """Test different message display effects."""
    logger.info("Testing message effects...")
    
    # Test each effect
    effects = ["rainbow", "pulse", "wipe", "border"]
    
    for effect in effects:
        logger.info(f"Testing '{effect}' effect...")
        matrix.display_message(f"Test message with {effect} effect", "TEST001", effect)
        time.sleep(8)  # Give enough time for the effect to complete
    
    logger.info("Message effects test completed")
    return True

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Test RGB LED Matrix display')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    parser.add_argument('--test', choices=['all', 'logo', 'text', 'status', 'message'], 
                      default='all', help='Test to run')
    args = parser.parse_args()
    
    # Check if the RGB matrix library is available
    if not RGBMATRIX_AVAILABLE:
        logger.error("RGB Matrix library not available. Please install it first.")
        logger.error("See: https://github.com/hzeller/rpi-rgb-led-matrix/tree/master/bindings/python")
        sys.exit(1)
    
    # Load configuration
    logger.info(f"Loading configuration from {args.config}")
    config = load_config(args.config)
    
    # Check if LED matrix is enabled in config
    matrix_config = get_led_matrix_config(config)
    if not matrix_config.get("Enabled", False):
        logger.warning("LED Matrix is not enabled in the configuration.")
        logger.warning("Enabling it for this test...")
        matrix_config["Enabled"] = True
    
    # Create a mock database for testing
    db = MockDatabase()
    
    # Initialize the display
    logger.info("Initializing LED Matrix display...")
    display = LEDMatrixDisplay(config, db)
    
    # Start the display
    logger.info("Starting LED Matrix display...")
    if not display.start():
        logger.error("Failed to start LED Matrix display")
        sys.exit(1)
    
    try:
        # Run the selected test(s)
        if args.test in ['all', 'logo']:
            test_logo_display(display)
            
        if args.test in ['all', 'text']:
            test_text_display(display)
            
        if args.test in ['all', 'status']:
            test_status_cycle(display)
            
        if args.test in ['all', 'message']:
            test_message_effects(display)
            
        logger.info("All tests completed successfully!")
        
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        # Stop the display
        logger.info("Stopping LED Matrix display...")
        display.stop()

if __name__ == "__main__":
    main()
