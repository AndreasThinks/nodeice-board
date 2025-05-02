import re
import time
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Callable

from nodeice_board.database import Database


class CommandHandler:
    """
    Handle commands from Meshtastic messages for the Nodeice Board.
    """
    
    # Command patterns
    HELP_CMD = re.compile(r'^!help\s*$', re.IGNORECASE)
    POST_CMD = re.compile(r'^!post\s+(.+)$', re.IGNORECASE)
    LIST_CMD = re.compile(r'^!list(?:\s+(\d+))?\s*$', re.IGNORECASE)
    VIEW_CMD = re.compile(r'^!view\s+(\d+)\s*$', re.IGNORECASE)
    COMMENT_CMD = re.compile(r'^!comment\s+(\d+)\s+(.+)$', re.IGNORECASE)
    
    def __init__(self, database: Database, send_message_callback: Callable[[str, str], bool]):
        """
        Initialize the command handler.
        
        Args:
            database: The database instance.
            send_message_callback: Callback function to send a message.
                Args: message (str), destination (str)
                Returns: success (bool)
        """
        self.db = database
        self.send_message = send_message_callback
        self.logger = logging.getLogger("NodeiceBoard")
        self.rate_limits = {}  # Store {sender_id: last_command_time}
        self.rate_limit_seconds = 1  # Minimum seconds between commands

    def handle_message(self, message: str, sender_id: str) -> bool:
        """
        Handle an incoming message.
        
        Args:
            message: The received message content.
            sender_id: The ID of the sender.
            
        Returns:
            True if message was handled as a command, False otherwise.
        """
        try:
            self.logger.debug(f"CommandHandler.handle_message called with: '{message}' from {sender_id}")
            
            # Validate input
            if not message or not message.strip():
                self.logger.warning(f"Received empty message from {sender_id}")
                return False
                
            # Add input length validation
            if len(message) > 1000:  # Set appropriate max length
                self.logger.warning(f"Message too long from {sender_id}: {len(message)} chars")
                self.send_message("Message too long. Please keep messages under 1000 characters.", sender_id)
                return False
                
            # Check rate limit
            current_time = time.time()
            if sender_id in self.rate_limits:
                time_since_last = current_time - self.rate_limits[sender_id]
                if time_since_last < self.rate_limit_seconds:
                    self.logger.warning(f"Rate limit exceeded for {sender_id}")
                    return False
                    
            # Update last command time
            self.rate_limits[sender_id] = current_time
                
            # Try to match different command patterns
            if CommandHandler.HELP_CMD.match(message):
                self.logger.debug(f"Matched !help command from {sender_id}")
                return self.handle_help_command(sender_id)
                
            match = CommandHandler.POST_CMD.match(message)
            if match:
                content = match.group(1).strip()
                self.logger.debug(f"Matched !post command from {sender_id}: {content[:20]}...")
                return self.handle_post_command(content, sender_id)
                
            match = CommandHandler.LIST_CMD.match(message)
            if match:
                try:
                    limit = int(match.group(1)) if match.group(1) else 5
                    # Validate limit is reasonable
                    if limit <= 0 or limit > 20:
                        self.send_message("Invalid limit. Please use a number between 1 and 20.", sender_id)
                        return False
                    self.logger.debug(f"Matched !list command from {sender_id} with limit {limit}")
                    return self.handle_list_command(sender_id, limit)
                except ValueError:
                    self.send_message("Invalid limit. Please use a number.", sender_id)
                    return False
                
            match = CommandHandler.VIEW_CMD.match(message)
            if match:
                try:
                    post_id = int(match.group(1))
                    if post_id <= 0:
                        self.send_message("Invalid post ID. Please use a positive number.", sender_id)
                        return False
                    self.logger.debug(f"Matched !view command from {sender_id} for post #{post_id}")
                    return self.handle_view_command(post_id, sender_id)
                except ValueError:
                    self.send_message("Invalid post ID. Please use a number.", sender_id)
                    return False
                
            match = CommandHandler.COMMENT_CMD.match(message)
            if match:
                try:
                    post_id = int(match.group(1))
                    if post_id <= 0:
                        self.send_message("Invalid post ID. Please use a positive number.", sender_id)
                        return False
                    content = match.group(2).strip()
                    content = self.sanitize_content(content)
                    self.logger.debug(f"Matched !comment command from {sender_id} for post #{post_id}: {content[:20]}...")
                    return self.handle_comment_command(post_id, content, sender_id)
                except ValueError:
                    self.send_message("Invalid post ID. Please use a number.", sender_id)
                    return False
            
            # If no command matched, let the user know
            self.logger.debug(f"No command matched for message from {sender_id}: {message}")
            self.send_message(
                "Unknown command. Send !help for available commands.",
                sender_id
            )
            return False
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.logger.error(f"Message: '{message}', Sender: {sender_id}")
            
            # Try to notify the user
            try:
                self.send_message(
                    "An error occurred while processing your command. Please try again later.",
                    sender_id
                )
            except Exception as send_error:
                self.logger.error(f"Failed to send error message: {send_error}")
                
            return False
        
    def handle_help_command(self, sender_id: str) -> bool:
        """
        Handle the !help command.
        
        Args:
            sender_id: The ID of the sender.
            
        Returns:
            True if message was sent successfully.
        """
        try:
            self.logger.info(f"handle_help_command called for sender {sender_id}")
            
            # Format help text with one command per line for better chunking
            help_text = (
                "Nodeice Board Commands:\n"
                "!post <message> - Create a new post\n"
                "!list [n] - Show n recent posts (default: 5)\n"
                "!view <post_id> - View a post and its comments\n"
                "!comment <post_id> <message> - Comment on a post\n"
                "!help - Show this help message"
            )
            
            result = self.send_message(help_text, sender_id)
            self.logger.debug(f"Help message sent to {sender_id}: {'Success' if result else 'Failed'}")
            return result
        except Exception as e:
            self.logger.error(f"Error handling help command: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
        
    def sanitize_content(self, content: str) -> str:
        """
        Sanitize user input to prevent injection attacks.
        
        Args:
            content: The raw user input.
            
        Returns:
            Sanitized content.
        """
        # Remove any potentially dangerous characters or patterns
        content = content.strip()
        
        # Limit length
        if len(content) > 1000:
            content = content[:1000]
            
        return content
        
    def handle_post_command(self, content: str, sender_id: str) -> bool:
        """
        Handle the !post command.
        
        Args:
            content: The content of the post.
            sender_id: The ID of the sender.
            
        Returns:
            True if the post was created successfully.
        """
        try:
            # Sanitize content before storing
            content = self.sanitize_content(content)
            post_id = self.db.create_post(content, sender_id)
            response = f"Post #{post_id} created successfully!"
            return self.send_message(response, sender_id)
        except Exception as e:
            self.logger.error(f"Error creating post: {e}")
            error_msg = "Failed to create post. Please try again later."
            self.send_message(error_msg, sender_id)
            return False
            
    def handle_list_command(self, sender_id: str, limit: int = 5) -> bool:
        """
        Handle the !list command.
        
        Args:
            sender_id: The ID of the sender.
            limit: Maximum number of posts to list.
            
        Returns:
            True if the message was sent successfully.
        """
        try:
            posts = self.db.get_recent_posts(limit)
            
            if not posts:
                return self.send_message("No posts found.", sender_id)
                
            # Send header as a separate message
            self.send_message("Recent posts:", sender_id)
            time.sleep(0.5)  # Small delay between messages
            
            # Send each post as a separate line/message
            for post in posts:
                # Format the timestamp
                timestamp = self._format_time_ago(post["created_at"])
                
                # Truncate content if needed
                content = post["content"]
                if len(content) > 30:
                    content = content[:27] + "..."
                    
                author = post["author_name"] or post["author_id"]
                post_line = f"#{post['id']}: {content} ({author}, {timestamp})"
                
                self.send_message(post_line, sender_id)
                time.sleep(0.5)  # Small delay between messages
                
            return True
        except Exception as e:
            self.logger.error(f"Error listing posts: {e}")
            error_msg = "Failed to retrieve posts. Please try again later."
            self.send_message(error_msg, sender_id)
            return False
            
    def handle_view_command(self, post_id: int, sender_id: str) -> bool:
        """
        Handle the !view command.
        
        Args:
            post_id: The ID of the post to view.
            sender_id: The ID of the sender.
            
        Returns:
            True if the message was sent successfully.
        """
        try:
            post = self.db.get_post(post_id)
            
            if not post:
                return self.send_message(f"Post #{post_id} not found.", sender_id)
                
            # Format the post header
            author = post["author_name"] or post["author_id"]
            timestamp = datetime.strptime(post["created_at"], "%Y-%m-%d %H:%M:%S")
            formatted_time = timestamp.strftime("%b %d, %Y, %I:%M %p")
            
            # Send post details as separate messages
            self.send_message(f"Post #{post_id}: {post['content']}", sender_id)
            time.sleep(0.5)
            
            self.send_message(f"By: {author}", sender_id)
            time.sleep(0.5)
            
            self.send_message(f"Posted: {formatted_time}", sender_id)
            time.sleep(0.5)
            
            # Get comments
            comments = self.db.get_comments_for_post(post_id)
            
            if comments:
                self.send_message("Comments:", sender_id)
                time.sleep(0.5)
                
                # Send each comment as a separate message
                for comment in comments:
                    comment_author = comment["author_name"] or comment["author_id"]
                    comment_time = self._format_time_ago(comment["created_at"])
                    comment_text = f"- {comment_author} ({comment_time}): {comment['content']}"
                    
                    self.send_message(comment_text, sender_id)
                    time.sleep(0.5)
            else:
                self.send_message("No comments yet.", sender_id)
                
            return True
        except Exception as e:
            self.logger.error(f"Error viewing post: {e}")
            error_msg = "Failed to retrieve post. Please try again later."
            self.send_message(error_msg, sender_id)
            return False
            
    def handle_comment_command(self, post_id: int, content: str, sender_id: str) -> bool:
        """
        Handle the !comment command.
        
        Args:
            post_id: The ID of the post to comment on.
            content: The content of the comment.
            sender_id: The ID of the sender.
            
        Returns:
            True if the comment was created successfully.
        """
        try:
            # Check if post exists
            post = self.db.get_post(post_id)
            
            if not post:
                return self.send_message(f"Post #{post_id} not found.", sender_id)
                
            # Create comment
            comment_id = self.db.create_comment(post_id, content, sender_id)
            response = f"Comment added to post #{post_id}"
            
            return self.send_message(response, sender_id)
        except Exception as e:
            self.logger.error(f"Error creating comment: {e}")
            error_msg = "Failed to create comment. Please try again later."
            self.send_message(error_msg, sender_id)
            return False
            
    def _format_time_ago(self, timestamp_str: str) -> str:
        """
        Format a timestamp as a human-readable "time ago" string.
        
        Args:
            timestamp_str: The timestamp string from the database.
            
        Returns:
            A human-readable string like "2h ago" or "3d ago".
        """
        try:
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            delta = now - timestamp
            
            seconds = delta.total_seconds()
            
            if seconds < 60:
                return "just now"
            elif seconds < 3600:
                minutes = int(seconds / 60)
                return f"{minutes}m ago"
            elif seconds < 86400:
                hours = int(seconds / 3600)
                return f"{hours}h ago"
            elif seconds < 604800:  # 7 days
                days = int(seconds / 86400)
                return f"{days}d ago"
            else:
                return timestamp.strftime("%b %d")
                
        except Exception as e:
            self.logger.error(f"Error formatting timestamp: {e}")
            return timestamp_str
