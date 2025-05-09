#!/usr/bin/env python3
"""
LED Matrix Display module for Nodeice Board.

This module handles the RGB LED matrix display functionality, including:
- Displaying the Meshtastic logo and "Nodice Board" title
- Cycling through status messages
- Displaying new messages with visual effects
- Handling button inputs for interactive features
"""

import os
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple, Callable
import subprocess
import math
import random

# Import PIL for image processing
from PIL import Image, ImageDraw, ImageFont, ImageOps

# Import the rgbmatrix library
try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
    RGBMATRIX_AVAILABLE = True
except ImportError:
    RGBMATRIX_AVAILABLE = False
    print("Warning: rgbmatrix module not available. LED Matrix display will be disabled.")


class LEDMatrixDisplay:
    """
    Class to manage the RGB LED Matrix display for Nodeice Board.
    """
    
    def __init__(self, config: Dict[str, Any], database):
        """
        Initialize the LED Matrix display.
        
        Args:
            config: The application configuration dictionary.
            database: The database instance for retrieving statistics.
        """
        self.logger = logging.getLogger("NodeiceBoard")
        self.config = config
        self.db = database
        self.matrix = None
        self.offscreen_canvas = None
        self.thread = None
        self.stop_event = threading.Event()
        self.message_event = threading.Event()
        self.current_message = None
        self.current_message_sender = None
        self.current_effect = None
        
        # Load matrix configuration
        self.matrix_config = self._get_matrix_config()
        
        # Initialize matrix if available
        if RGBMATRIX_AVAILABLE:
            self._init_matrix()
        else:
            self.logger.warning("RGB Matrix library not available. Display disabled.")
            
        # Load assets
        self._load_assets()
        
        # Set up status cycle
        self.status_index = 0
        self.status_last_change = time.time()
        self.status_cycle_seconds = self.matrix_config.get("Status_Cycle_Seconds", 5)
        
        # Button handling
        self.button_handlers = {}
        self.last_button_press = 0
        self.button_debounce_ms = 200  # Debounce time in milliseconds
        
    def _get_matrix_config(self) -> Dict[str, Any]:
        """
        Get the LED matrix configuration from the config dictionary.
        
        Returns:
            A dictionary with the LED matrix configuration.
        """
        default_config = {
            "Enabled": False,
            "Hardware_Mapping": "adafruit-hat",
            "Rows": 32,
            "Cols": 32,
            "Chain_Length": 1,
            "Parallel": 1,
            "Brightness": 50,
            "GPIO_Slowdown": 2,
            "Display_Mode": "standard",
            "Status_Cycle_Seconds": 5,
            "Message_Effect": "rainbow",
            "Interactive": True,
            "Auto_Brightness": True
        }
        
        matrix_config = {}
        
        try:
            if 'Nodeice_board' in self.config and 'LED_Matrix' in self.config['Nodeice_board']:
                matrix_config = self.config['Nodeice_board']['LED_Matrix']
        except Exception as e:
            self.logger.error(f"Error loading LED matrix config: {e}")
            
        # Merge with defaults
        for key, value in default_config.items():
            if key not in matrix_config:
                matrix_config[key] = value
                
        return matrix_config
        
    def _init_matrix(self):
        """Initialize the RGB matrix with the configured options."""
        try:
            options = RGBMatrixOptions()
            
            # Set options from config
            options.hardware_mapping = self.matrix_config.get("Hardware_Mapping", "adafruit-hat")
            options.rows = self.matrix_config.get("Rows", 32)
            options.cols = self.matrix_config.get("Cols", 32)
            options.chain_length = self.matrix_config.get("Chain_Length", 1)
            options.parallel = self.matrix_config.get("Parallel", 1)
            options.brightness = self.matrix_config.get("Brightness", 50)
            options.gpio_slowdown = self.matrix_config.get("GPIO_Slowdown", 2)
            
            # Additional options for better performance
            options.pwm_lsb_nanoseconds = 130
            options.pwm_bits = 11
            
            # Create the matrix
            self.matrix = RGBMatrix(options=options)
            self.offscreen_canvas = self.matrix.CreateFrameCanvas()
            
            self.logger.info(f"RGB Matrix initialized: {options.rows}x{options.cols}, chain={options.chain_length}")
        except Exception as e:
            self.logger.error(f"Error initializing RGB Matrix: {e}")
            self.matrix = None
            
    def _load_assets(self):
        """Load and prepare assets for display."""
        try:
            # Set up fonts
            self.font_small = graphics.Font()
            self.font_small.LoadFont("../../../fonts/5x8.bdf")  # Adjust path as needed
            
            self.font_medium = graphics.Font()
            self.font_medium.LoadFont("../../../fonts/7x13.bdf")  # Adjust path as needed
            
            self.font_large = graphics.Font()
            self.font_large.LoadFont("../../../fonts/9x18.bdf")  # Adjust path as needed
            
            # Define colors
            self.color_white = graphics.Color(255, 255, 255)
            self.color_red = graphics.Color(255, 0, 0)
            self.color_green = graphics.Color(0, 255, 0)
            self.color_blue = graphics.Color(0, 0, 255)
            self.color_yellow = graphics.Color(255, 255, 0)
            self.color_cyan = graphics.Color(0, 255, 255)
            self.color_magenta = graphics.Color(255, 0, 255)
            
            # Load Meshtastic logo
            logo_path = os.path.join("assets", "Mesh_Logo_Playstore.png")
            if os.path.exists(logo_path):
                self.logo = Image.open(logo_path)
                # Resize logo to fit in the corner of the display
                logo_size = 10  # Small logo in the corner
                self.logo = self.logo.resize((logo_size, logo_size), Image.LANCZOS)
                self.logger.info(f"Loaded Meshtastic logo from {logo_path}")
            else:
                self.logger.warning(f"Meshtastic logo not found at {logo_path}")
                self.logo = None
                
        except Exception as e:
            self.logger.error(f"Error loading assets: {e}")
            
    def start(self):
        """Start the LED matrix display thread."""
        if not RGBMATRIX_AVAILABLE or not self.matrix:
            self.logger.warning("RGB Matrix not available. Display not started.")
            return False
            
        if self.thread and self.thread.is_alive():
            self.logger.warning("LED Matrix display thread already running")
            return True
            
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._display_loop)
        self.thread.daemon = True
        self.thread.start()
        
        self.logger.info("LED Matrix display started")
        return True
        
    def stop(self):
        """Stop the LED matrix display thread."""
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join(timeout=5.0)
            if self.thread.is_alive():
                self.logger.warning("LED Matrix display thread did not terminate cleanly")
            else:
                self.logger.info("LED Matrix display stopped")
                
        # Clear the display
        if self.matrix:
            self.matrix.Clear()
            
    def _display_loop(self):
        """Main display loop that runs in a separate thread."""
        try:
            while not self.stop_event.is_set():
                # Check if we have a message to display
                if self.message_event.is_set():
                    self._display_message_with_effect()
                    self.message_event.clear()
                else:
                    # Display status cycle
                    self._display_status()
                    
                # Check for button input if interactive mode is enabled
                if self.matrix_config.get("Interactive", True):
                    self._check_button_input()
                    
                # Small sleep to prevent CPU hogging
                time.sleep(0.05)
        except Exception as e:
            self.logger.error(f"Error in display loop: {e}")
            
    def _display_status(self):
        """Display the current status screen and cycle through status messages."""
        if not self.matrix:
            return
            
        # Check if it's time to change the status display
        current_time = time.time()
        if current_time - self.status_last_change >= self.status_cycle_seconds:
            self.status_index = (self.status_index + 1) % 5  # 5 different status screens
            self.status_last_change = current_time
            
        # Clear the canvas
        self.offscreen_canvas.Clear()
        
        # Always show the logo in the top-left corner
        if self.logo:
            self._draw_image(self.logo, 0, 0)
            
        # Always show "Nodice Board" title at the top
        graphics.DrawText(self.offscreen_canvas, self.font_small, 12, 8, self.color_cyan, "Nodice Board")
        
        # Display different status information based on the current index
        if self.status_index == 0:
            # Total messages
            try:
                total_posts = self.db.get_total_posts_count()
                graphics.DrawText(self.offscreen_canvas, self.font_medium, 2, 20, self.color_white, f"Messages: {total_posts}")
            except Exception as e:
                self.logger.error(f"Error getting total posts: {e}")
                
        elif self.status_index == 1:
            # System uptime
            uptime = self._get_system_uptime()
            graphics.DrawText(self.offscreen_canvas, self.font_medium, 2, 20, self.color_green, "Uptime:")
            graphics.DrawText(self.offscreen_canvas, self.font_medium, 2, 30, self.color_green, uptime)
            
        elif self.status_index == 2:
            # Connected nodes (placeholder - would need to be implemented in MeshtasticInterface)
            graphics.DrawText(self.offscreen_canvas, self.font_medium, 2, 20, self.color_yellow, "Nodes:")
            graphics.DrawText(self.offscreen_canvas, self.font_medium, 2, 30, self.color_yellow, "Connected")
            
        elif self.status_index == 3:
            # Next post expiration
            expiration_days = self._get_expiration_days()
            graphics.DrawText(self.offscreen_canvas, self.font_medium, 2, 20, self.color_magenta, "Next Wipe:")
            graphics.DrawText(self.offscreen_canvas, self.font_medium, 2, 30, self.color_magenta, f"{expiration_days} days")
            
        elif self.status_index == 4:
            # Current time
            current_time = datetime.now().strftime("%H:%M:%S")
            current_date = datetime.now().strftime("%Y-%m-%d")
            graphics.DrawText(self.offscreen_canvas, self.font_medium, 2, 20, self.color_blue, current_time)
            graphics.DrawText(self.offscreen_canvas, self.font_small, 2, 30, self.color_blue, current_date)
            
        # Update the display
        self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)
        
    def _get_system_uptime(self) -> str:
        """
        Get the system uptime as a formatted string.
        
        Returns:
            A string representing the system uptime.
        """
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                days = int(uptime_seconds // 86400)
                hours = int((uptime_seconds % 86400) // 3600)
                minutes = int((uptime_seconds % 3600) // 60)
                
                if days > 0:
                    return f"{days}d {hours}h"
                else:
                    return f"{hours}h {minutes}m"
        except Exception as e:
            self.logger.error(f"Error getting uptime: {e}")
            return "Unknown"
            
    def _get_expiration_days(self) -> int:
        """
        Get the number of days until the next post expiration.
        
        Returns:
            The number of days until posts expire.
        """
        try:
            if 'Nodeice_board' in self.config and 'Expiration_Days' in self.config['Nodeice_board']:
                return self.config['Nodeice_board']['Expiration_Days']
            return 7  # Default
        except Exception as e:
            self.logger.error(f"Error getting expiration days: {e}")
            return 7  # Default
            
    def display_message(self, message: str, sender_id: str, effect: str = None):
        """
        Display a message on the LED matrix.
        
        Args:
            message: The message to display.
            sender_id: The ID of the sender.
            effect: The visual effect to use (optional).
        """
        if not self.matrix:
            return False
            
        # Store the message and sender
        self.current_message = message
        self.current_message_sender = sender_id
        
        # Use configured effect if none specified
        if not effect:
            effect = self.matrix_config.get("Message_Effect", "rainbow")
        self.current_effect = effect
        
        # Signal the display thread to show the message
        self.message_event.set()
        
        return True
        
    def _display_message_with_effect(self):
        """Display the current message with the specified visual effect."""
        if not self.matrix or not self.current_message:
            return
            
        message = self.current_message
        effect = self.current_effect
        
        # Apply the selected effect
        if effect == "pulse":
            self._effect_pulse_message(message)
        elif effect == "wipe":
            self._effect_wipe_message(message)
        elif effect == "border":
            self._effect_border_message(message)
        else:  # Default to rainbow
            self._effect_rainbow_message(message)
            
    def _effect_rainbow_message(self, message: str):
        """Display a message with rainbow-colored text that scrolls across the screen."""
        if not self.matrix:
            return
            
        # Prepare for scrolling
        pos = self.offscreen_canvas.width
        my_text = message
        
        # Calculate the total width of the text
        text_width = graphics.DrawText(self.offscreen_canvas, self.font_medium, 0, 0, self.color_white, my_text)
        
        # Rainbow colors
        rainbow_colors = [
            graphics.Color(255, 0, 0),      # Red
            graphics.Color(255, 127, 0),    # Orange
            graphics.Color(255, 255, 0),    # Yellow
            graphics.Color(0, 255, 0),      # Green
            graphics.Color(0, 0, 255),      # Blue
            graphics.Color(75, 0, 130),     # Indigo
            graphics.Color(148, 0, 211)     # Violet
        ]
        
        # Scroll the text until it's completely off-screen
        while pos + text_width > 0 and not self.stop_event.is_set():
            # Clear the canvas
            self.offscreen_canvas.Clear()
            
            # Draw the text with rainbow colors
            for i in range(len(my_text)):
                color_index = (i + int(time.time() * 5)) % len(rainbow_colors)
                color = rainbow_colors[color_index]
                graphics.DrawText(
                    self.offscreen_canvas, 
                    self.font_medium, 
                    pos + i * 7,  # Approximate character width
                    20, 
                    color, 
                    my_text[i]
                )
            
            # Update position
            pos -= 1
            
            # Update the display
            self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)
            
            # Small delay
            time.sleep(0.05)
            
    def _effect_pulse_message(self, message: str):
        """Display a message with a pulsing effect before scrolling."""
        if not self.matrix:
            return
            
        # Pulse effect
        for i in range(10):  # 10 pulses
            brightness = int(math.sin(i * 0.314) * 100) + 100  # Oscillate between 0 and 200
            brightness = max(10, min(brightness, 100))  # Clamp between 10 and 100
            
            # Set brightness
            self.matrix.brightness = brightness
            
            # Fill with color that gets brighter
            color_val = min(255, int(brightness * 2.55))
            self.offscreen_canvas.Fill(color_val, 0, color_val)
            
            # Update the display
            self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)
            
            # Small delay
            time.sleep(0.1)
            
        # Reset brightness
        self.matrix.brightness = self.matrix_config.get("Brightness", 50)
        
        # Now scroll the message
        self._effect_rainbow_message(message)
        
    def _effect_wipe_message(self, message: str):
        """Display a message with a colorful wipe transition."""
        if not self.matrix:
            return
            
        # Wipe effect - horizontal color bars
        for x in range(self.offscreen_canvas.width):
            self.offscreen_canvas.Clear()
            for y in range(self.offscreen_canvas.height):
                # Create a rainbow pattern
                r = 128 + 127 * math.sin(y * 0.1 + time.time() * 3)
                g = 128 + 127 * math.sin(y * 0.1 + 2 + time.time() * 3)
                b = 128 + 127 * math.sin(y * 0.1 + 4 + time.time() * 3)
                color = graphics.Color(int(r), int(g), int(b))
                
                # Draw vertical line
                for i in range(x + 1):
                    self.offscreen_canvas.SetPixel(i, y, color.red, color.green, color.blue)
            
            # Update the display
            self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)
            
            # Small delay
            time.sleep(0.02)
            
        # Now scroll the message
        self._effect_rainbow_message(message)
        
    def _effect_border_message(self, message: str):
        """Display a message with a flashing border effect while scrolling."""
        if not self.matrix:
            return
            
        # Prepare for scrolling
        pos = self.offscreen_canvas.width
        my_text = message
        
        # Calculate the total width of the text
        text_width = graphics.DrawText(self.offscreen_canvas, self.font_medium, 0, 0, self.color_white, my_text)
        
        # Scroll the text until it's completely off-screen
        while pos + text_width > 0 and not self.stop_event.is_set():
            # Clear the canvas
            self.offscreen_canvas.Clear()
            
            # Draw flashing border
            border_color = self._get_cycling_color(time.time() * 5)
            self._draw_border(border_color)
            
            # Draw the text
            graphics.DrawText(self.offscreen_canvas, self.font_medium, pos, 20, self.color_white, my_text)
            
            # Update position
            pos -= 1
            
            # Update the display
            self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)
            
            # Small delay
            time.sleep(0.05)
            
    def _get_cycling_color(self, phase: float) -> graphics.Color:
        """
        Get a color that cycles through the rainbow based on the phase.
        
        Args:
            phase: The phase of the color cycle.
            
        Returns:
            A Color object representing the current color in the cycle.
        """
        r = int(128 + 127 * math.sin(phase))
        g = int(128 + 127 * math.sin(phase + 2))
        b = int(128 + 127 * math.sin(phase + 4))
        return graphics.Color(r, g, b)
        
    def _draw_border(self, color: graphics.Color):
        """
        Draw a border around the edge of the display.
        
        Args:
            color: The color of the border.
        """
        width = self.offscreen_canvas.width
        height = self.offscreen_canvas.height
        
        # Draw top and bottom borders
        for x in range(width):
            self.offscreen_canvas.SetPixel(x, 0, color.red, color.green, color.blue)
            self.offscreen_canvas.SetPixel(x, height - 1, color.red, color.green, color.blue)
            
        # Draw left and right borders
        for y in range(height):
            self.offscreen_canvas.SetPixel(0, y, color.red, color.green, color.blue)
            self.offscreen_canvas.SetPixel(width - 1, y, color.red, color.green, color.blue)
            
    def _draw_image(self, image: Image.Image, x: int, y: int):
        """
        Draw a PIL Image on the matrix at the specified position.
        
        Args:
            image: The PIL Image to draw.
            x: The x-coordinate to start drawing at.
            y: The y-coordinate to start drawing at.
        """
        if not self.matrix:
            return
            
        # Convert image to RGB mode if it's not already
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        # Get image dimensions
        width, height = image.size
        
        # Draw the image pixel by pixel
        for img_x in range(width):
            for img_y in range(height):
                # Get pixel color
                r, g, b = image.getpixel((img_x, img_y))
                
                # Calculate position on the matrix
                matrix_x = x + img_x
                matrix_y = y + img_y
                
                # Check if the pixel is within the matrix bounds
                if (0 <= matrix_x < self.offscreen_canvas.width and 
                    0 <= matrix_y < self.offscreen_canvas.height):
                    # Set the pixel
                    self.offscreen_canvas.SetPixel(matrix_x, matrix_y, r, g, b)
                    
    def _check_button_input(self):
        """Check for button input and handle it."""
        if not self.matrix_config.get("Interactive", True):
            return
            
        # This is a placeholder for actual button handling
        # In a real implementation, you would check GPIO pins or other input methods
        
        # Example of how button handling would work:
        # current_time_ms = int(time.time() * 1000)
        # if current_time_ms - self.last_button_press > self.button_debounce_ms:
        #     # Check button states
        #     if gpio.input(BUTTON_1_PIN) == gpio.LOW:
        #         self._handle_button_press(1)
        #         self.last_button_press = current_time_ms
        
    def _handle_button_press(self, button_id: int):
        """
        Handle a button press event.
        
        Args:
            button_id: The ID of the button that was pressed.
        """
        self.logger.debug(f"Button {button_id} pressed")
        
        if button_id == 1:
            # Button 1: Manually cycle status display
            self.status_index = (self.status_index + 1) % 5
            self.status_last_change = time.time()
            
        elif button_id == 2:
            # Button 2: Adjust brightness
            current_brightness = self.matrix.brightness
            new_brightness = (current_brightness + 25) % 125
            if new_brightness < 25:
                new_brightness = 25
            self.matrix.brightness = new_brightness
            self.logger.info(f"Brightness set to {new_brightness}")
            
        elif button_id == 3:
            # Button 3: Toggle message scrolling (placeholder)
            pass
            
        # Call any registered handlers for this button
        if button_id in self.button_handlers:
            self.button_handlers[button_id]()
            
    def register_button_handler(self, button_id: int, handler: Callable):
        """
        Register a handler function for a button press.
        
        Args:
            button_id: The ID of the button.
            handler: The function to call when the button is pressed.
        """
        self.button_handlers[button_id] = handler
