import re
import time
import logging
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

    def handle_message(self, message: str, sender_id: str) -> bool:
        """
        Handle an incoming message.
        
        Args:
            message: The received message content.
            sender_id: The ID of the sender.
            
        Returns:
            True if message was handled as a command, False otherwise.
        """
        # Try to match different command patterns
        if CommandHandler.HELP_CMD.match(message):
            return self.handle_help_command(sender_id)
            
        match = CommandHandler.POST_CMD.match(message)
        if match:
            content = match.group(1).strip()
            return self.handle_post_command(content, sender_id)
            
        match = CommandHandler.LIST_CMD.match(message)
        if match:
            limit = int(match.group(1)) if match.group(1) else 5
            return self.handle_list_command(sender_id, limit)
            
        match = CommandHandler.VIEW_CMD.match(message)
        if match:
            post_id = int(match.group(1))
            return self.handle_view_command(post_id, sender_id)
            
        match = CommandHandler.COMMENT_CMD.match(message)
        if match:
            post_id = int(match.group(1))
            content = match.group(2).strip()
            return self.handle_comment_command(post_id, content, sender_id)
        
        # If no command matched, let the user know
        self.send_message(
            "Unknown command. Send !help for available commands.",
            sender_id
        )
        return False
        
    def handle_help_command(self, sender_id: str) -> bool:
        """
        Handle the !help command.
        
        Args:
            sender_id: The ID of the sender.
            
        Returns:
            True if message was sent successfully.
        """
        help_text = (
            "Nodeice Board Commands:\n"
            "!post <message> - Create a new post\n"
            "!list [n] - Show n recent posts (default: 5)\n"
            "!view <post_id> - View a post and its comments\n"
            "!comment <post_id> <message> - Comment on a post\n"
            "!help - Show this help message"
        )
        
        return self.send_message(help_text, sender_id)
        
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
                
            response = "Recent posts:\n"
            for post in posts:
                # Format the timestamp
                timestamp = self._format_time_ago(post["created_at"])
                
                # Truncate content if needed
                content = post["content"]
                if len(content) > 30:
                    content = content[:27] + "..."
                    
                author = post["author_name"] or post["author_id"]
                response += f"#{post['id']}: {content} ({author}, {timestamp})\n"
                
            return self.send_message(response, sender_id)
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
                
            # Format the post
            author = post["author_name"] or post["author_id"]
            timestamp = datetime.strptime(post["created_at"], "%Y-%m-%d %H:%M:%S")
            formatted_time = timestamp.strftime("%b %d, %Y, %I:%M %p")
            
            response = (
                f"Post #{post_id}: {post['content']}\n"
                f"By: {author}\n"
                f"Posted: {formatted_time}\n\n"
            )
            
            # Get and format comments
            comments = self.db.get_comments_for_post(post_id)
            
            if comments:
                response += "Comments:\n"
                for comment in comments:
                    comment_author = comment["author_name"] or comment["author_id"]
                    comment_time = self._format_time_ago(comment["created_at"])
                    response += f"- {comment_author} ({comment_time}): {comment['content']}\n"
            else:
                response += "No comments yet."
                
            return self.send_message(response, sender_id)
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
