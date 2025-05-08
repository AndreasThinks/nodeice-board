import re
import time
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Callable

from nodeice_board.database import Database
from nodeice_board.config import load_config, get_info_url, get_expiration_days


class CommandHandler:
    """
    Handle commands from Meshtastic messages for the Nodeice Board.
    """
    
    # Command patterns
    HELP_CMD = re.compile(r'^!help\s*$', re.IGNORECASE)
    INFO_CMD = re.compile(r'^!info\s*$', re.IGNORECASE)
    POST_CMD = re.compile(r'^!post\s+(.+)$', re.IGNORECASE)
    LIST_CMD = re.compile(r'^!list(?:\s+(\d+))?\s*$', re.IGNORECASE)
    VIEW_CMD = re.compile(r'^!view\s+(\d+)\s*$', re.IGNORECASE)
    COMMENT_CMD = re.compile(r'^!comment\s+(\d+)\s+(.+)$', re.IGNORECASE)
    SUBSCRIBE_ALL_CMD = re.compile(r'^!subscribe\s+all\s*$', re.IGNORECASE)
    SUBSCRIBE_POST_CMD = re.compile(r'^!subscribe\s+(\d+)\s*$', re.IGNORECASE)
    UNSUBSCRIBE_ALL_CMD = re.compile(r'^!unsubscribe\s+all\s*$', re.IGNORECASE)
    UNSUBSCRIBE_POST_CMD = re.compile(r'^!unsubscribe\s+(\d+)\s*$', re.IGNORECASE)
    LIST_SUBSCRIPTIONS_CMD = re.compile(r'^!subscriptions\s*$', re.IGNORECASE)
    STATUS_CMD = re.compile(r'^!status\s*$', re.IGNORECASE)
    
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
        
        # Load config to get info URL and expiration days
        self.config = load_config()
        self.info_url = get_info_url(self.config)
        self.expiration_days = get_expiration_days(self.config)

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
                
            if CommandHandler.INFO_CMD.match(message):
                self.logger.debug(f"Matched !info command from {sender_id}")
                return self.handle_info_command(sender_id)
                
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
                    
            # Subscription commands
            match = CommandHandler.SUBSCRIBE_ALL_CMD.match(message)
            if match:
                self.logger.debug(f"Matched !subscribe all command from {sender_id}")
                return self.handle_subscribe_all_command(sender_id)
                
            match = CommandHandler.SUBSCRIBE_POST_CMD.match(message)
            if match:
                try:
                    post_id = int(match.group(1))
                    if post_id <= 0:
                        self.send_message("Invalid post ID. Please use a positive number.", sender_id)
                        return False
                    self.logger.debug(f"Matched !subscribe {post_id} command from {sender_id}")
                    return self.handle_subscribe_post_command(post_id, sender_id)
                except ValueError:
                    self.send_message("Invalid post ID. Please use a number.", sender_id)
                    return False
                    
            match = CommandHandler.UNSUBSCRIBE_ALL_CMD.match(message)
            if match:
                self.logger.debug(f"Matched !unsubscribe all command from {sender_id}")
                return self.handle_unsubscribe_all_command(sender_id)
                
            match = CommandHandler.UNSUBSCRIBE_POST_CMD.match(message)
            if match:
                try:
                    post_id = int(match.group(1))
                    if post_id <= 0:
                        self.send_message("Invalid post ID. Please use a positive number.", sender_id)
                        return False
                    self.logger.debug(f"Matched !unsubscribe {post_id} command from {sender_id}")
                    return self.handle_unsubscribe_post_command(post_id, sender_id)
                except ValueError:
                    self.send_message("Invalid post ID. Please use a number.", sender_id)
                    return False
                    
            match = CommandHandler.LIST_SUBSCRIPTIONS_CMD.match(message)
            if match:
                self.logger.debug(f"Matched !subscriptions command from {sender_id}")
                return self.handle_list_subscriptions_command(sender_id)
                
            match = CommandHandler.STATUS_CMD.match(message)
            if match:
                self.logger.debug(f"Matched !status command from {sender_id}")
                return self.handle_status_command(sender_id)
            
            # If no command matched, just log it but don't respond
            self.logger.debug(f"No command matched for message from {sender_id}: {message}")
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
            
            # Send introduction message first
            intro_text = (
                "This is a public notice board. You can post topics or leave comments.\n\n"
                f"Learn more here: {self.info_url}"
            )
            self.send_message(intro_text, sender_id)
            time.sleep(0.5)  # Small delay between messages
            
            # Format help text with one command per line for better chunking
            help_text = (
                "Nodeice Board Commands:\n"
                "!post <message> - Create a new post\n"
                "!list [n] - Show n recent posts (default: 5)\n"
                "!view <post_id> - View a post and its comments\n"
                "!comment <post_id> <message> - Comment on a post\n"
                "!subscribe all - Subscribe to all new posts\n"
                "!subscribe <post_id> - Subscribe to a specific post\n"
                "!unsubscribe all - Unsubscribe from all notifications\n"
                "!unsubscribe <post_id> - Unsubscribe from a specific post\n"
                "!subscriptions - List your current subscriptions\n"
                "!status - Show network status information\n"
                "!info - Show board statistics\n"
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
            
            # Notify subscribers who are subscribed to all posts
            self.notify_subscribers_for_new_post(post_id, content, sender_id)
            
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
                
            # Send header as a separate message with deletion info
            days_until_deletion = self.expiration_days  # Simple approximation
            self.send_message(f"Recent posts (next deletion in {days_until_deletion} days):", sender_id)
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
            
            # Notify subscribers who are subscribed to this post
            self.notify_subscribers_for_new_comment(post_id, content, sender_id)
            
            return self.send_message(response, sender_id)
        except Exception as e:
            self.logger.error(f"Error creating comment: {e}")
            error_msg = "Failed to create comment. Please try again later."
            self.send_message(error_msg, sender_id)
            return False
            
    def handle_subscribe_all_command(self, sender_id: str) -> bool:
        """
        Handle the !subscribe all command.
        
        Args:
            sender_id: The ID of the sender.
            
        Returns:
            True if the subscription was created successfully.
        """
        try:
            result = self.db.subscribe_to_all_posts(sender_id)
            
            if result:
                response = "You are now subscribed to all new posts."
            else:
                response = "You are already subscribed to all new posts."
                
            return self.send_message(response, sender_id)
        except Exception as e:
            self.logger.error(f"Error subscribing to all posts: {e}")
            error_msg = "Failed to subscribe. Please try again later."
            self.send_message(error_msg, sender_id)
            return False
            
    def handle_subscribe_post_command(self, post_id: int, sender_id: str) -> bool:
        """
        Handle the !subscribe <post_id> command.
        
        Args:
            post_id: The ID of the post to subscribe to.
            sender_id: The ID of the sender.
            
        Returns:
            True if the subscription was created successfully.
        """
        try:
            result = self.db.subscribe_to_post(sender_id, post_id)
            
            if result:
                response = f"You are now subscribed to post #{post_id}."
            else:
                response = f"You are already subscribed to post #{post_id}."
                
            return self.send_message(response, sender_id)
        except ValueError as ve:
            error_msg = str(ve)
            self.send_message(error_msg, sender_id)
            return False
        except Exception as e:
            self.logger.error(f"Error subscribing to post: {e}")
            error_msg = "Failed to subscribe. Please try again later."
            self.send_message(error_msg, sender_id)
            return False
            
    def handle_unsubscribe_all_command(self, sender_id: str) -> bool:
        """
        Handle the !unsubscribe all command.
        
        Args:
            sender_id: The ID of the sender.
            
        Returns:
            True if the unsubscription was successful.
        """
        try:
            count = self.db.unsubscribe_from_all(sender_id)
            
            if count > 0:
                response = f"You have been unsubscribed from {count} subscription(s)."
            else:
                response = "You don't have any active subscriptions."
                
            return self.send_message(response, sender_id)
        except Exception as e:
            self.logger.error(f"Error unsubscribing from all: {e}")
            error_msg = "Failed to unsubscribe. Please try again later."
            self.send_message(error_msg, sender_id)
            return False
            
    def handle_unsubscribe_post_command(self, post_id: int, sender_id: str) -> bool:
        """
        Handle the !unsubscribe <post_id> command.
        
        Args:
            post_id: The ID of the post to unsubscribe from.
            sender_id: The ID of the sender.
            
        Returns:
            True if the unsubscription was successful.
        """
        try:
            result = self.db.unsubscribe_from_post(sender_id, post_id)
            
            if result:
                response = f"You have been unsubscribed from post #{post_id}."
            else:
                response = f"You were not subscribed to post #{post_id}."
                
            return self.send_message(response, sender_id)
        except Exception as e:
            self.logger.error(f"Error unsubscribing from post: {e}")
            error_msg = "Failed to unsubscribe. Please try again later."
            self.send_message(error_msg, sender_id)
            return False
            
    def handle_list_subscriptions_command(self, sender_id: str) -> bool:
        """
        Handle the !subscriptions command.
        
        Args:
            sender_id: The ID of the sender.
            
        Returns:
            True if the subscriptions were listed successfully.
        """
        try:
            subscriptions = self.db.get_user_subscriptions(sender_id)
            
            if not subscriptions:
                return self.send_message("You don't have any active subscriptions.", sender_id)
                
            # Send header as a separate message
            self.send_message("Your subscriptions:", sender_id)
            time.sleep(0.5)  # Small delay between messages
            
            # Send each subscription as a separate message
            for sub in subscriptions:
                if sub["all_posts"]:
                    sub_text = "All new posts"
                else:
                    # Truncate content if needed
                    content = sub["post_content"] or "Unknown post"
                    if len(content) > 30:
                        content = content[:27] + "..."
                    sub_text = f"Post #{sub['post_id']}: {content}"
                
                self.send_message(sub_text, sender_id)
                time.sleep(0.5)  # Small delay between messages
                
            return True
        except Exception as e:
            self.logger.error(f"Error listing subscriptions: {e}")
            error_msg = "Failed to retrieve subscriptions. Please try again later."
            self.send_message(error_msg, sender_id)
            return False
            
    def notify_subscribers_for_new_post(self, post_id: int, content: str, author_id: str) -> None:
        """
        Notify subscribers about a new post.
        
        Args:
            post_id: The ID of the new post.
            content: The content of the post.
            author_id: The ID of the post author.
        """
        try:
            # Get all users subscribed to all posts
            subscribers = self.db.get_subscribers_for_all_posts()
            
            # Don't notify the author
            if author_id in subscribers:
                subscribers.remove(author_id)
                
            if not subscribers:
                return
                
            # Truncate content if needed
            if len(content) > 50:
                content = content[:47] + "..."
                
            # Send notification to each subscriber
            notification = f"New post #{post_id}: {content}"
            
            for subscriber_id in subscribers:
                try:
                    self.send_message(notification, subscriber_id)
                    time.sleep(0.5)  # Small delay between messages
                except Exception as e:
                    self.logger.error(f"Error notifying subscriber {subscriber_id}: {e}")
        except Exception as e:
            self.logger.error(f"Error notifying subscribers for new post: {e}")
            
    def notify_subscribers_for_new_comment(self, post_id: int, content: str, author_id: str) -> None:
        """
        Notify subscribers about a new comment on a post.
        
        Args:
            post_id: The ID of the post that was commented on.
            content: The content of the comment.
            author_id: The ID of the comment author.
        """
        try:
            # Get all users subscribed to this post
            subscribers = self.db.get_subscribers_for_post(post_id)
            
            # Don't notify the author
            if author_id in subscribers:
                subscribers.remove(author_id)
                
            if not subscribers:
                return
                
            # Truncate content if needed
            if len(content) > 50:
                content = content[:47] + "..."
                
            # Send notification to each subscriber
            notification = f"New comment on post #{post_id}: {content}"
            
            for subscriber_id in subscribers:
                try:
                    self.send_message(notification, subscriber_id)
                    time.sleep(0.5)  # Small delay between messages
                except Exception as e:
                    self.logger.error(f"Error notifying subscriber {subscriber_id}: {e}")
        except Exception as e:
            self.logger.error(f"Error notifying subscribers for new comment: {e}")
            
    def handle_info_command(self, sender_id: str) -> bool:
        """
        Handle the !info command.
        
        Args:
            sender_id: The ID of the sender.
            
        Returns:
            True if message was sent successfully.
        """
        try:
            self.logger.info(f"handle_info_command called for sender {sender_id}")
            
            # Get total number of messages posted ever
            total_posts = self.db.get_total_posts_count()
            
            # Calculate time until next wipe
            days_until_deletion = self.expiration_days
            
            # Get system uptime
            uptime = "Unknown"
            try:
                with open('/proc/uptime', 'r') as f:
                    uptime_seconds = float(f.readline().split()[0])
                    days = int(uptime_seconds // 86400)
                    hours = int((uptime_seconds % 86400) // 3600)
                    minutes = int((uptime_seconds % 3600) // 60)
                    uptime = f"{days}d {hours}h {minutes}m"
            except Exception as e:
                self.logger.error(f"Error getting uptime: {e}")
                # Fallback method for systems without /proc/uptime
                try:
                    import subprocess
                    result = subprocess.run(['uptime', '-p'], capture_output=True, text=True)
                    if result.returncode == 0:
                        uptime = result.stdout.strip()
                except Exception as e2:
                    self.logger.error(f"Error getting uptime via subprocess: {e2}")
            
            # Format and send the info message
            info_text = (
                "Nodeice Board Info:\n"
                f"Total messages posted: {total_posts}\n"
                f"Next wipe in: {days_until_deletion} days\n"
                f"System uptime: {uptime}"
            )
            
            return self.send_message(info_text, sender_id)
        except Exception as e:
            self.logger.error(f"Error handling info command: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
            
    def handle_status_command(self, sender_id: str) -> bool:
        """
        Handle the !status command.
        
        Args:
            sender_id: The ID of the sender.
            
        Returns:
            True if message was sent successfully.
        """
        try:
            self.logger.info(f"handle_status_command called for sender {sender_id}")
            
            # Get database connection
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Get node count
            try:
                cursor.execute("SELECT COUNT(*) FROM node_status WHERE status = 'active'")
                active_nodes = cursor.fetchone()[0]
            except Exception as e:
                self.logger.error(f"Error getting active nodes count: {e}")
                active_nodes = "Unknown"
            
            # Get post count
            cursor.execute("SELECT COUNT(*) FROM posts WHERE visible = 1")
            active_posts = cursor.fetchone()[0]
            
            # Get comment count
            cursor.execute("SELECT COUNT(*) FROM comments")
            comments = cursor.fetchone()[0]
            
            # Get system uptime
            uptime = "Unknown"
            try:
                cursor.execute(
                    "SELECT metric_value FROM metrics WHERE metric_name = 'system_uptime_seconds' ORDER BY timestamp DESC LIMIT 1"
                )
                result = cursor.fetchone()
                if result:
                    uptime_seconds = result[0]
                    days = int(uptime_seconds // 86400)
                    hours = int((uptime_seconds % 86400) // 3600)
                    minutes = int((uptime_seconds % 3600) // 60)
                    uptime = f"{days}d {hours}h {minutes}m"
            except Exception as e:
                self.logger.error(f"Error getting uptime from metrics: {e}")
                # Fallback to direct system check
                try:
                    with open('/proc/uptime', 'r') as f:
                        uptime_seconds = float(f.readline().split()[0])
                        days = int(uptime_seconds // 86400)
                        hours = int((uptime_seconds % 86400) // 3600)
                        minutes = int((uptime_seconds % 3600) // 60)
                        uptime = f"{days}d {hours}h {minutes}m"
                except Exception as e2:
                    self.logger.error(f"Error getting uptime from /proc: {e2}")
            
            # Format the status message
            status_text = (
                "Nodeice Board Status:\n"
                f"Active nodes: {active_nodes}\n"
                f"Active posts: {active_posts}\n"
                f"Total comments: {comments}\n"
                f"System uptime: {uptime}"
            )
            
            # Send the status message
            return self.send_message(status_text, sender_id)
        except Exception as e:
            self.logger.error(f"Error handling status command: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
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
