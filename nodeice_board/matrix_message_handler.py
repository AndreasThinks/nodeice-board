#!/usr/bin/env python3
"""
Matrix Message Handler module for Nodeice Board.

This module connects the LED matrix display to the message handling system,
triggering display updates when new messages are received.
"""

import logging
import threading
import time
from typing import Optional, Dict, Any

from nodeice_board.led_matrix_display import LEDMatrixDisplay


class MatrixMessageHandler:
    """
    Handler for connecting the LED matrix display to the message system.
    """
    
    def __init__(self, matrix_display: LEDMatrixDisplay, command_handler=None):
        """
        Initialize the matrix message handler.
        
        Args:
            matrix_display: The LED matrix display instance.
            command_handler: The command handler instance (optional).
        """
        self.logger = logging.getLogger("NodeiceBoard")
        self.matrix_display = matrix_display
        self.command_handler = command_handler
        self.original_handle_message = None
        self.original_handle_post_command = None
        self.original_handle_comment_command = None
        
    def register_handlers(self):
        """
        Register message handlers to intercept messages and display them on the matrix.
        This method patches the command handler's methods to intercept messages.
        """
        if not self.command_handler:
            self.logger.warning("No command handler provided, cannot register matrix message handlers")
            return False
            
        try:
            # Store original methods for chaining
            self.original_handle_message = self.command_handler.handle_message
            self.original_handle_post_command = self.command_handler.handle_post_command
            self.original_handle_comment_command = self.command_handler.handle_comment_command
            
            # Patch the methods
            self.command_handler.handle_message = self._patched_handle_message
            self.command_handler.handle_post_command = self._patched_handle_post_command
            self.command_handler.handle_comment_command = self._patched_handle_comment_command
            
            self.logger.info("Matrix message handlers registered successfully")
            return True
        except Exception as e:
            self.logger.error(f"Error registering matrix message handlers: {e}")
            return False
            
    def _patched_handle_message(self, message: str, sender_id: str) -> bool:
        """
        Patched version of handle_message that displays messages on the matrix.
        
        Args:
            message: The received message content.
            sender_id: The ID of the sender.
            
        Returns:
            The result from the original handle_message method.
        """
        # Call the original method first
        result = self.original_handle_message(message, sender_id)
        
        # If it's not a command, display it on the matrix
        if not message.startswith('!'):
            self.display_message(message, sender_id)
            
        return result
        
    def _patched_handle_post_command(self, content: str, sender_id: str) -> bool:
        """
        Patched version of handle_post_command that displays new posts on the matrix.
        
        Args:
            content: The content of the post.
            sender_id: The ID of the sender.
            
        Returns:
            The result from the original handle_post_command method.
        """
        # Call the original method first
        result = self.original_handle_post_command(content, sender_id)
        
        # If successful, display the post on the matrix
        if result:
            self.display_post(content, sender_id)
            
        return result
        
    def _patched_handle_comment_command(self, post_id: int, content: str, sender_id: str) -> bool:
        """
        Patched version of handle_comment_command that displays new comments on the matrix.
        
        Args:
            post_id: The ID of the post being commented on.
            content: The content of the comment.
            sender_id: The ID of the sender.
            
        Returns:
            The result from the original handle_comment_command method.
        """
        # Call the original method first
        result = self.original_handle_comment_command(post_id, content, sender_id)
        
        # If successful, display the comment on the matrix
        if result:
            self.display_comment(post_id, content, sender_id)
            
        return result
        
    def display_message(self, message: str, sender_id: str):
        """
        Display a regular message on the LED matrix.
        
        Args:
            message: The message to display.
            sender_id: The ID of the sender.
        """
        if not self.matrix_display:
            return
            
        try:
            self.logger.debug(f"Displaying message on matrix: {message[:30]}...")
            self.matrix_display.display_message(message, sender_id, effect="rainbow")
        except Exception as e:
            self.logger.error(f"Error displaying message on matrix: {e}")
            
    def display_post(self, content: str, sender_id: str):
        """
        Display a new post on the LED matrix with a special effect.
        
        Args:
            content: The content of the post.
            sender_id: The ID of the sender.
        """
        if not self.matrix_display:
            return
            
        try:
            self.logger.debug(f"Displaying new post on matrix: {content[:30]}...")
            # Use a more attention-grabbing effect for posts
            self.matrix_display.display_message(f"New Post: {content}", sender_id, effect="pulse")
        except Exception as e:
            self.logger.error(f"Error displaying post on matrix: {e}")
            
    def display_comment(self, post_id: int, content: str, sender_id: str):
        """
        Display a new comment on the LED matrix.
        
        Args:
            post_id: The ID of the post being commented on.
            content: The content of the comment.
            sender_id: The ID of the sender.
        """
        if not self.matrix_display:
            return
            
        try:
            self.logger.debug(f"Displaying comment on matrix: {content[:30]}...")
            # Use a different effect for comments
            self.matrix_display.display_message(f"Comment on #{post_id}: {content}", sender_id, effect="border")
        except Exception as e:
            self.logger.error(f"Error displaying comment on matrix: {e}")
            
    def on_new_message(self, message: str, sender_id: str):
        """
        Handle a new message directly (can be called from outside the patched methods).
        
        Args:
            message: The message to display.
            sender_id: The ID of the sender.
        """
        self.display_message(message, sender_id)
