import sqlite3
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any


class Database:
    def __init__(self, db_path: str = "nodeice_board.db"):
        """Initialize the database connection."""
        self.db_path = db_path
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """Initialize the database if it doesn't exist."""
        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        
        # Connect to the database
        self.conn = sqlite3.connect(self.db_path)
        
        # Create tables if they don't exist
        cursor = self.conn.cursor()
        
        # Posts table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            author_id TEXT NOT NULL,
            author_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
        
        # Index for finding posts by date (for expiration)
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts (created_at)
        ''')
        
        self.conn.commit()

    def create_post(self, content: str, author_id: str, author_name: Optional[str] = None) -> int:
        """
        Create a new post.
        
        Args:
            content: The content of the post.
            author_id: The Meshtastic node ID of the author.
            author_name: The human-readable name of the author (if available).
            
        Returns:
            The ID of the created post.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO posts (content, author_id, author_name) VALUES (?, ?, ?)",
            (content, author_id, author_name)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_post(self, post_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a post by ID.
        
        Args:
            post_id: The ID of the post.
            
        Returns:
            The post as a dictionary, or None if not found.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM posts WHERE id = ?", (post_id,))
        post = cursor.fetchone()
        
        if not post:
            return None
            
        return {
            "id": post[0],
            "content": post[1],
            "author_id": post[2],
            "author_name": post[3],
            "created_at": post[4]
        }

    def get_recent_posts(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get the most recent posts.
        
        Args:
            limit: The maximum number of posts to retrieve.
            
        Returns:
            A list of posts as dictionaries.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM posts ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        posts = cursor.fetchall()
        
        return [
            {
                "id": post[0],
                "content": post[1],
                "author_id": post[2],
                "author_name": post[3],
                "created_at": post[4]
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
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO comments (post_id, content, author_id, author_name) VALUES (?, ?, ?, ?)",
            (post_id, content, author_id, author_name)
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_comments_for_post(self, post_id: int) -> List[Dict[str, Any]]:
        """
        Get all comments for a post.
        
        Args:
            post_id: The ID of the post.
            
        Returns:
            A list of comments as dictionaries.
        """
        cursor = self.conn.cursor()
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

    def delete_expired_posts(self, days: int = 7) -> int:
        """
        Delete posts older than the specified number of days.
        
        Args:
            days: The number of days after which posts should be deleted.
            
        Returns:
            The number of posts deleted.
        """
        cursor = self.conn.cursor()
        cursor.execute(
            "DELETE FROM posts WHERE created_at < datetime('now', ? || ' days')",
            (f"-{days}",)
        )
        deleted_count = cursor.rowcount
        self.conn.commit()
        return deleted_count

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
