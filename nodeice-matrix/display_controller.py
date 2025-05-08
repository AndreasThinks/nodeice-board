"""
Display Controller for Nodeice Matrix Display.

This module manages the RGB LED matrix display, including different display modes,
animations, and transitions.
"""

import os
import time
import logging
import threading
from typing import Dict, Any, List, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics

logger = logging.getLogger("NodeiceMatrix")

class DisplayController:
    """
    Controls the RGB LED matrix display for the Nodeice Board.
    
    This class manages different display modes, including:
    - Status mode: Shows rotating metrics and the Meshtastic logo
    - Message mode: Shows new messages with animations
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the display controller.
        
        Args:
            config: The configuration dictionary.
        """
        self.config = config
        self.display_config = config["display"]
        self.current_mode = "status"
        self.active_posts_count = 0
        self.metrics = {}
        self.current_metric_index = 0
        self.message_queue = []
        self.message_display_active = False
        self.message_display_thread = None
        self.running = False
        self.setup_matrix()
        self.load_assets()
        
    def setup_matrix(self):
        """Initialize the RGB matrix with configuration settings."""
        options = RGBMatrixOptions()
        options.hardware_mapping = self.display_config.get("hardware_mapping", "adafruit-hat")
        options.rows = self.display_config.get("rows", 32)
        options.cols = self.display_config.get("cols", 32)
        options.chain_length = self.display_config.get("chain_length", 1)
        options.parallel = self.display_config.get("parallel", 1)
        options.brightness = self.display_config.get("brightness", 70)
        options.gpio_slowdown = self.display_config.get("gpio_slowdown", 2)
        
        self.matrix = RGBMatrix(options=options)
        self.offscreen_canvas = self.matrix.CreateFrameCanvas()
        self.width = self.matrix.width
        self.height = self.matrix.height
        
        # Create fonts
        self.font_small = graphics.Font()
        self.font_small.LoadFont("fonts/4x6.bdf")  # Small font for metrics
        
        self.font_medium = graphics.Font()
        self.font_medium.LoadFont("fonts/6x9.bdf")  # Medium font for title
        
        self.font_large = graphics.Font()
        self.font_large.LoadFont("fonts/8x13.bdf")  # Large font for messages
        
        # Create colors
        self.white = graphics.Color(255, 255, 255)
        self.green = graphics.Color(0, 255, 0)
        self.red = graphics.Color(255, 0, 0)
        self.blue = graphics.Color(0, 0, 255)
        self.yellow = graphics.Color(255, 255, 0)
        self.cyan = graphics.Color(0, 255, 255)
        self.magenta = graphics.Color(255, 0, 255)
        
        # Get title color from config
        title_color = self.display_config.get("title_color", [255, 255, 255])
        self.title_color = graphics.Color(title_color[0], title_color[1], title_color[2])
        
        # Get counter color from config
        counter_color = self.display_config.get("counter_color", [0, 255, 0])
        self.counter_color = graphics.Color(counter_color[0], counter_color[1], counter_color[2])
        
    def load_assets(self):
        """Load assets like the Meshtastic logo."""
        try:
            # Load the Meshtastic logo
            logo_path = "./assets/Mesh_Logo_Playstore.png"
            if os.path.exists(logo_path):
                self.logo = Image.open(logo_path)
                # Resize the logo to fit in the corner (about 1/4 of the display)
                logo_size = min(self.width // 4, self.height // 4)
                self.logo = self.logo.resize((logo_size, logo_size), Image.LANCZOS)
                logger.info(f"Loaded Meshtastic logo with size {logo_size}x{logo_size}")
            else:
                logger.warning(f"Meshtastic logo not found at {logo_path}")
                self.logo = None
        except Exception as e:
            logger.error(f"Error loading assets: {e}")
            self.logo = None
            
    def update(self, update_type: str, data: Any):
        """
        Handle different types of updates from the database monitor.
        
        Args:
            update_type: The type of update ("new_message", "metrics_update", "active_posts").
            data: The data associated with the update.
        """
        if update_type == "new_message":
            self.queue_message(data)
        elif update_type == "metrics_update":
            self.metrics = data
        elif update_type == "active_posts":
            self.active_posts_count = data
            
    def queue_message(self, message: Dict[str, Any]):
        """
        Add a new message to the queue and switch to message mode.
        
        Args:
            message: The message to display.
        """
        self.message_queue.append(message)
        logger.info(f"Queued message: {message['content'][:30]}...")
        
        # If not already displaying a message, start now
        if not self.message_display_active:
            self.display_next_message()
            
    def display_next_message(self):
        """Display the next message in the queue with animation."""
        if not self.message_queue:
            self.message_display_active = False
            return
            
        self.message_display_active = True
        message = self.message_queue.pop(0)
        
        # Start a new thread to handle the message animation
        if self.message_display_thread and self.message_display_thread.is_alive():
            self.message_display_thread.join(timeout=1.0)
            
        self.message_display_thread = threading.Thread(
            target=self._animate_message,
            args=(message,)
        )
        self.message_display_thread.daemon = True
        self.message_display_thread.start()
        
    def _animate_message(self, message: Dict[str, Any]):
        """
        Animate a message on the display.
        
        Args:
            message: The message to animate.
        """
        content = message["content"]
        author = message.get("author_name", "Unknown")
        
        # Save the current mode and switch to message mode
        previous_mode = self.current_mode
        self.current_mode = "message"
        
        # Get message display time from config
        display_time = self.display_config.get("message_display_time", 15)
        scroll_speed = self.display_config.get("scroll_speed", 2)
        
        try:
            # Create a canvas for the message
            message_canvas = self.matrix.CreateFrameCanvas()
            
            # Splash effect animation
            self._animate_splash_effect(message_canvas)
            
            # Scroll the message
            self._scroll_text(message_canvas, content, author, scroll_speed)
            
            # Display the message for a while
            end_time = time.time() + display_time
            while time.time() < end_time and self.running:
                # If there are more messages in the queue, shorten the display time
                if len(self.message_queue) > 0:
                    break
                time.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error animating message: {e}")
            
        finally:
            # Switch back to the previous mode
            self.current_mode = previous_mode
            self.message_display_active = False
            
            # If there are more messages in the queue, display the next one
            if self.message_queue:
                self.display_next_message()
                
    def _animate_splash_effect(self, canvas):
        """
        Create a splash effect animation for new messages.
        
        Args:
            canvas: The canvas to draw on.
        """
        # Clear the canvas
        canvas.Fill(0, 0, 0)
        
        # Draw expanding circles from the center
        center_x = self.width // 2
        center_y = self.height // 2
        
        colors = [self.red, self.green, self.blue, self.yellow, self.cyan, self.magenta]
        
        for radius in range(1, max(self.width, self.height) // 2 + 5, 2):
            canvas.Fill(0, 0, 0)
            
            # Draw circle
            color = colors[radius % len(colors)]
            for angle in range(0, 360, 5):
                x = int(center_x + radius * graphics.cos(angle))
                y = int(center_y + radius * graphics.sin(angle))
                
                if 0 <= x < self.width and 0 <= y < self.height:
                    graphics.DrawLine(canvas, x, y, center_x, center_y, color)
                    
            # Swap the canvas
            canvas = self.matrix.SwapOnVSync(canvas)
            time.sleep(0.05)
            
    def _scroll_text(self, canvas, text, author, speed):
        """
        Scroll text across the display.
        
        Args:
            canvas: The canvas to draw on.
            text: The text to scroll.
            author: The author of the message.
            speed: The scroll speed in pixels per frame.
        """
        # Prepare the text
        full_text = f"{text} - From: {author}"
        
        # Calculate text width
        text_width = 0
        for char in full_text:
            text_width += self.font_large.CharacterWidth(ord(char))
            
        # Start position (off the right edge)
        pos_x = self.width
        
        # Scroll until the text is off the left edge
        while pos_x + text_width > 0 and self.running:
            # Clear the canvas
            canvas.Fill(0, 0, 0)
            
            # Draw the text with a colorful effect
            for i, char in enumerate(full_text):
                char_width = self.font_large.CharacterWidth(ord(char))
                char_x = pos_x + sum(self.font_large.CharacterWidth(ord(c)) for c in full_text[:i])
                
                # Skip if the character is off-screen
                if char_x + char_width < 0 or char_x >= self.width:
                    continue
                    
                # Choose a color based on position
                color_index = (i + int(time.time() * 5)) % 6
                color = [self.red, self.green, self.blue, self.yellow, self.cyan, self.magenta][color_index]
                
                # Draw the character
                graphics.DrawText(canvas, self.font_large, char_x, self.height // 2 + 4, color, char)
                
            # Swap the canvas
            canvas = self.matrix.SwapOnVSync(canvas)
            
            # Move the text to the left
            pos_x -= speed
            
            # Small delay
            time.sleep(0.03)
            
    def display_status(self):
        """Display the status screen with rotating metrics."""
        # Clear the canvas
        self.offscreen_canvas.Fill(0, 0, 0)
        
        # Display the Meshtastic logo if available
        if self.logo:
            logo_position = self.display_config.get("logo_position", "top-left")
            x, y = 0, 0
            
            if logo_position == "top-right":
                x = self.width - self.logo.width
            elif logo_position == "bottom-left":
                y = self.height - self.logo.height
            elif logo_position == "bottom-right":
                x = self.width - self.logo.width
                y = self.height - self.logo.height
                
            self.offscreen_canvas.SetImage(self.logo, x, y)
            
        # Display the title "Nodice Board"
        title = "Nodice Board"
        title_width = sum(self.font_medium.CharacterWidth(ord(c)) for c in title)
        title_x = (self.width - title_width) // 2
        graphics.DrawText(self.offscreen_canvas, self.font_medium, title_x, 8, self.title_color, title)
        
        # Display the active posts counter
        self.display_posts_counter()
        
        # Display a rotating metric
        if self.metrics:
            metric_names = list(self.metrics.keys())
            if metric_names:
                # Rotate through metrics
                if self.current_metric_index >= len(metric_names):
                    self.current_metric_index = 0
                    
                metric_name = metric_names[self.current_metric_index]
                metric_value = self.metrics[metric_name]
                
                # Format the metric name for display (replace underscores with spaces)
                display_name = metric_name.replace("_", " ").title()
                
                # Format the metric value
                if isinstance(metric_value, float):
                    display_value = f"{metric_value:.2f}"
                else:
                    display_value = str(metric_value)
                    
                # Display the metric name and value
                y_pos = self.height // 2 + 2
                graphics.DrawText(self.offscreen_canvas, self.font_small, 1, y_pos, self.white, display_name)
                graphics.DrawText(self.offscreen_canvas, self.font_small, 1, y_pos + 8, self.green, display_value)
                
                # Increment the metric index for the next update
                self.current_metric_index += 1
                
    def display_posts_counter(self):
        """Display the active posts counter."""
        counter_text = f"Posts: {self.active_posts_count}"
        counter_position = self.display_config.get("counter_position", "bottom-right")
        
        counter_width = sum(self.font_small.CharacterWidth(ord(c)) for c in counter_text)
        
        x, y = 1, self.height - 2
        
        if counter_position == "top-right":
            x = self.width - counter_width - 1
            y = 6
        elif counter_position == "bottom-left":
            x = 1
            y = self.height - 2
        elif counter_position == "bottom-right":
            x = self.width - counter_width - 1
            y = self.height - 2
            
        graphics.DrawText(self.offscreen_canvas, self.font_small, x, y, self.counter_color, counter_text)
        
    def run(self):
        """Main display loop."""
        self.running = True
        last_update_time = 0
        rotation_interval = self.display_config.get("rotation_interval", 5)
        
        try:
            while self.running:
                # Only update the display in status mode
                # (message mode is handled by its own thread)
                if self.current_mode == "status":
                    current_time = time.time()
                    
                    # Update the display if it's time
                    if current_time - last_update_time >= rotation_interval:
                        self.display_status()
                        last_update_time = current_time
                        
                        # Swap the canvas
                        self.offscreen_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)
                        
                # Small delay to prevent high CPU usage
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("Display controller interrupted")
        finally:
            self.running = False
            self.matrix.Clear()
            
    def stop(self):
        """Stop the display controller."""
        self.running = False
        if self.message_display_thread and self.message_display_thread.is_alive():
            self.message_display_thread.join(timeout=2.0)
        self.matrix.Clear()
        logger.info("Display controller stopped")
