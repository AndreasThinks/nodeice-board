import sqlite3
import os
import time
import threading
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any, Union


class Database:
    def __init__(self, db_path: str = "nodeice_board.db"):
        """Initialize the database connection."""
        self.db_path = db_path
        self.local = threading.local()  # Thread-local storage for connections
        self.logger = logging.getLogger("NodeiceBoard")
        self.init_db()
    
    def get_connection(self, max_retries=3, retry_delay=1):
        """
        Get a thread-local database connection with retry logic.
        
        Args:
            max_retries: Maximum number of connection attempts.
            retry_delay: Delay in seconds between retries.
            
        Returns:
            SQLite connection object.
            
        Raises:
            sqlite3.OperationalError: If connection fails after max_retries.
        """
        retries = 0
        last_error = None
        
        while retries < max_retries:
            try:
                if not hasattr(self.local, 'conn') or self.local.conn is None:
                    self.logger.debug(f"Creating new database connection for thread {threading.current_thread().name}")
                    self.local.conn = sqlite3.connect(
                        self.db_path,
                        timeout=10  # 10-second timeout
                    )
                    # Enable foreign keys
                    self.local.conn.execute("PRAGMA foreign_keys = ON")
                return self.local.conn
            except sqlite3.OperationalError as e:
                last_error = e
                retries += 1
                self.logger.warning(f"Database connection attempt {retries} failed: {e}")
                if retries >= max_retries:
                    self.logger.error(f"Failed to connect to database after {max_retries} attempts")
                    raise
                time.sleep(retry_delay)
                
        # This should not be reached due to the raise in the loop, but just in case
        raise last_error if last_error else sqlite3.OperationalError("Failed to connect to database")
    
    def init_db(self):
        """Initialize the database if it doesn't exist."""
        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        
        # Connect to the database
        conn = self.get_connection()
        
        # Create tables if they don't exist
        cursor = conn.cursor()
        
        # Posts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            author_id TEXT NOT NULL,
            author_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            visible BOOLEAN DEFAULT 1
        )
        ''')
        
        # Comments table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            author_id TEXT NOT NULL,
            author_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE
        )
        ''')
        
        # Subscriptions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            post_id INTEGER,
            all_posts BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts (id) ON DELETE CASCADE
        )
        ''')
        
        # Index for finding posts by date (for expiration)
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts (created_at)
        ''')
        
        # Index for finding subscriptions by user
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions (user_id)
        ''')
        
        # Index for finding subscriptions by post
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_subscriptions_post_id ON subscriptions (post_id)
        ''')
        
        conn.commit()

    def create_post(self, content: str, author_id: str, author_name: Optional[str] = None) -> int:
        """
        Create a new post.
        
        Args:
            content: The content of the post.
            author_id: The Meshtastic node ID of the author.
            author_name: The human-readable name of the author (if available).
            
        Returns:
            The ID of the created post.
            
        Raises:
            ValueError: If content is empty or too long.
        """
        # Validate inputs
        if not content or not content.strip():
            raise ValueError("Post content cannot be empty")
            
        if len(content) > 1000:  # Set appropriate max length
            content = content[:1000]
            
        if not author_id or not author_id.strip():
            raise ValueError("Author ID cannot be empty")
            
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO posts (content, author_id, author_name) VALUES (?, ?, ?)",
            (content, author_id, author_name)
        )
        conn.commit()
        return cursor.lastrowid

    def get_post(self, post_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a post by ID.
        
        Args:
            post_id: The ID of the post.
            
        Returns:
            The post as a dictionary, or None if not found.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE id = ? AND visible = 1", (post_id,))
        post = cursor.fetchone()
        
        if not post:
            return None
            
        return {
            "id": post[0],
            "content": post[1],
            "author_id": post[2],
            "author_name": post[3],
            "created_at": post[4],
            "visible": bool(post[5])
        }

    def get_recent_posts(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get the most recent visible posts.
        
        Args:
            limit: The maximum number of posts to retrieve.
            
        Returns:
            A list of posts as dictionaries.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM posts WHERE visible = 1 ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        posts = cursor.fetchall()
        
        return [
            {
                "id": post[0],
                "content": post[1],
                "author_id": post[2],
                "author_name": post[3],
                "created_at": post[4],
                "visible": bool(post[5])
            }
            for post in posts
        ]

    def create_comment(self, post_id: int, content: str, author_id: str, author_name: Optional[str] = None) -> int:
        """
        Create a new comment on a post.
        
        Args:
            post_id: The ID of the post to comment on.
            content: The content of the comment.
            author_id: The Meshtastic node ID of the author.
            author_name: The human-readable name of the author (if available).
            
        Returns:
            The ID of the created comment.
            
        Raises:
            ValueError: If content is empty or too long, or if post_id is invalid.
        """
        # Validate inputs
        if not isinstance(post_id, int) or post_id <= 0:
            raise ValueError("Invalid post ID")
            
        if not content or not content.strip():
            raise ValueError("Comment content cannot be empty")
            
        if len(content) > 1000:  # Set appropriate max length
            content = content[:1000]
            
        if not author_id or not author_id.strip():
            raise ValueError("Author ID cannot be empty")
            
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO comments (post_id, content, author_id, author_name) VALUES (?, ?, ?, ?)",
            (post_id, content, author_id, author_name)
        )
        conn.commit()
        return cursor.lastrowid

    def get_comments_for_post(self, post_id: int) -> List[Dict[str, Any]]:
        """
        Get all comments for a post.
        
        Args:
            post_id: The ID of the post.
            
        Returns:
            A list of comments as dictionaries.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM comments WHERE post_id = ? ORDER BY created_at ASC",
            (post_id,)
        )
        comments = cursor.fetchall()
        
        return [
            {
                "id": comment[0],
                "post_id": comment[1],
                "content": comment[2],
                "author_id": comment[3],
                "author_name": comment[4],
                "created_at": comment[5]
            }
            for comment in comments
        ]

    def mark_expired_posts_as_invisible(self, days: int = 7) -> int:
        """
        Mark posts older than the specified number of days as not visible.
        
        Args:
            days: The number of days after which posts should be marked as not visible.
            
        Returns:
            The number of posts marked as not visible.
            
        Raises:
            ValueError: If days parameter is invalid.
        """
        # Validate days parameter
        if not isinstance(days, int) or days < 0:
            self.logger.warning(f"Invalid days parameter: {days}, using default of 7")
            days = 7  # Default to 7 if invalid
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Use parameter directly without string concatenation
        days_str = str(days)
        cursor.execute(
            "UPDATE posts SET visible = 0 WHERE visible = 1 AND created_at < datetime('now', '-' || ? || ' days')",
            (days_str,)
        )
        updated_count = cursor.rowcount
        conn.commit()
        return updated_count

    def subscribe_to_all_posts(self, user_id: str) -> bool:
        """
        Subscribe a user to notifications for all new posts.
        
        Args:
            user_id: The Meshtastic node ID of the user.
            
        Returns:
            True if subscription was created successfully, False if already exists.
            
        Raises:
            ValueError: If user_id is invalid.
        """
        if not user_id or not user_id.strip():
            raise ValueError("User ID cannot be empty")
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if subscription already exists
        cursor.execute(
            "SELECT id FROM subscriptions WHERE user_id = ? AND all_posts = 1",
            (user_id,)
        )
        if cursor.fetchone():
            return False  # Already subscribed
            
        # Create subscription
        cursor.execute(
            "INSERT INTO subscriptions (user_id, post_id, all_posts) VALUES (?, NULL, 1)",
            (user_id,)
        )
        conn.commit()
        return True
        
    def subscribe_to_post(self, user_id: str, post_id: int) -> bool:
        """
        Subscribe a user to notifications for a specific post.
        
        Args:
            user_id: The Meshtastic node ID of the user.
            post_id: The ID of the post to subscribe to.
            
        Returns:
            True if subscription was created successfully, False if already exists.
            
        Raises:
            ValueError: If user_id or post_id is invalid.
        """
        if not user_id or not user_id.strip():
            raise ValueError("User ID cannot be empty")
            
        if not isinstance(post_id, int) or post_id <= 0:
            raise ValueError("Invalid post ID")
            
        # Check if post exists
        post = self.get_post(post_id)
        if not post:
            raise ValueError(f"Post #{post_id} not found")
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if subscription already exists
        cursor.execute(
            "SELECT id FROM subscriptions WHERE user_id = ? AND post_id = ?",
            (user_id, post_id)
        )
        if cursor.fetchone():
            return False  # Already subscribed
            
        # Create subscription
        cursor.execute(
            "INSERT INTO subscriptions (user_id, post_id, all_posts) VALUES (?, ?, 0)",
            (user_id, post_id)
        )
        conn.commit()
        return True
        
    def unsubscribe_from_all(self, user_id: str) -> int:
        """
        Unsubscribe a user from all notifications.
        
        Args:
            user_id: The Meshtastic node ID of the user.
            
        Returns:
            The number of subscriptions deleted.
            
        Raises:
            ValueError: If user_id is invalid.
        """
        if not user_id or not user_id.strip():
            raise ValueError("User ID cannot be empty")
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM subscriptions WHERE user_id = ?",
            (user_id,)
        )
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count
        
    def unsubscribe_from_post(self, user_id: str, post_id: int) -> bool:
        """
        Unsubscribe a user from notifications for a specific post.
        
        Args:
            user_id: The Meshtastic node ID of the user.
            post_id: The ID of the post to unsubscribe from.
            
        Returns:
            True if subscription was deleted, False if not found.
            
        Raises:
            ValueError: If user_id or post_id is invalid.
        """
        if not user_id or not user_id.strip():
            raise ValueError("User ID cannot be empty")
            
        if not isinstance(post_id, int) or post_id <= 0:
            raise ValueError("Invalid post ID")
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM subscriptions WHERE user_id = ? AND post_id = ?",
            (user_id, post_id)
        )
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted
        
    def get_user_subscriptions(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all subscriptions for a user.
        
        Args:
            user_id: The Meshtastic node ID of the user.
            
        Returns:
            A list of subscription dictionaries.
            
        Raises:
            ValueError: If user_id is invalid.
        """
        if not user_id or not user_id.strip():
            raise ValueError("User ID cannot be empty")
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT s.id, s.user_id, s.post_id, s.all_posts, s.created_at, 
                   p.content as post_content
            FROM subscriptions s
            LEFT JOIN posts p ON s.post_id = p.id
            WHERE s.user_id = ?
            ORDER BY s.created_at DESC
            """,
            (user_id,)
        )
        subscriptions = cursor.fetchall()
        
        return [
            {
                "id": sub[0],
                "user_id": sub[1],
                "post_id": sub[2],
                "all_posts": bool(sub[3]),
                "created_at": sub[4],
                "post_content": sub[5] if sub[2] else None
            }
            for sub in subscriptions
        ]
        
    def get_subscribers_for_all_posts(self) -> List[str]:
        """
        Get all users subscribed to all posts.
        
        Returns:
            A list of user IDs.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT DISTINCT user_id FROM subscriptions WHERE all_posts = 1"
        )
        subscribers = cursor.fetchall()
        
        return [sub[0] for sub in subscribers]
        
    def get_subscribers_for_post(self, post_id: int) -> List[str]:
        """
        Get all users subscribed to a specific post.
        
        Args:
            post_id: The ID of the post.
            
        Returns:
            A list of user IDs.
            
        Raises:
            ValueError: If post_id is invalid.
        """
        if not isinstance(post_id, int) or post_id <= 0:
            raise ValueError("Invalid post ID")
            
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT DISTINCT user_id FROM subscriptions WHERE post_id = ?",
            (post_id,)
        )
        subscribers = cursor.fetchall()
        
        return [sub[0] for sub in subscribers]

    def get_total_posts_count(self) -> int:
        """
        Get the total number of posts ever created (both visible and invisible).
        
        Returns:
            The total number of posts.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM posts")
        count = cursor.fetchone()[0]
        return count

    def close(self):
        """Close the database connection."""
        if hasattr(self.local, 'conn') and self.local.conn:
            self.local.conn.close()
            self.local.conn = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False  # Don't suppress exceptions
