"""
Database Monitor for Nodeice Matrix Display.

This module monitors the Nodeice Board SQLite database for changes,
including new messages and updated metrics.
"""

import os
import time
import sqlite3
import logging
import threading
from typing import List, Dict, Any, Callable, Tuple, Optional

logger = logging.getLogger("NodeiceMatrix")

class DatabaseMonitor:
    """
    Monitors the Nodeice Board SQLite database for changes.
    
    This class runs in a background thread and periodically checks the database
    for new messages and updated metrics. When changes are detected, it calls
    registered callback functions.
    """
    
    def __init__(self, db_path: str, poll_interval: int = 2):
        """
        Initialize the database monitor.
        
        Args:
            db_path: Path to the SQLite database file.
            poll_interval: How often to check for changes (in seconds).
        """
        self.db_path = db_path
        self.poll_interval = poll_interval
        self.callbacks = []
        self.running = False
        self.thread = None
        self.last_message_id = self._get_last_message_id()
        self.last_metrics_time = None
        
    def register_callback(self, callback: Callable[[str, Any], None]):
        """
        Register a callback function to be called when changes are detected.
        
        The callback function should accept two arguments:
        - update_type: A string indicating the type of update ("new_message", "metrics_update", "active_posts")
        - data: The data associated with the update
        
        Args:
            callback: The callback function.
        """
        self.callbacks.append(callback)
        
    def start_monitoring(self):
        """Start the database monitoring thread."""
        if self.running:
            logger.warning("Database monitor is already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop)
        self.thread.daemon = True
        self.thread.start()
        logger.info("Database monitor started")
        
    def stop(self):
        """Stop the database monitoring thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5.0)
            self.thread = None
        logger.info("Database monitor stopped")
        
    def _get_connection(self):
        """
        Get a connection to the SQLite database.
        
        Returns:
            A SQLite connection object.
            
        Raises:
            sqlite3.OperationalError: If the database cannot be opened.
        """
        # Ensure the database file exists
        if not os.path.exists(self.db_path):
            logger.error(f"Database file not found: {self.db_path}")
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
            
        return sqlite3.connect(self.db_path)
        
    def _get_last_message_id(self) -> int:
        """
        Get the ID of the last message in the database.
        
        Returns:
            The ID of the last message, or 0 if there are no messages.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(id) FROM posts")
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0] is not None:
                return result[0]
            return 0
        except Exception as e:
            logger.error(f"Error getting last message ID: {e}")
            return 0
            
    def _check_new_messages(self) -> List[Dict[str, Any]]:
        """
        Check for new messages in the database.
        
        Returns:
            A list of new messages as dictionaries.
        """
        new_messages = []
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, content, author_id, author_name, created_at FROM posts WHERE id > ? AND visible = 1 ORDER BY id ASC",
                (self.last_message_id,)
            )
            
            for row in cursor.fetchall():
                message = {
                    "id": row[0],
                    "content": row[1],
                    "author_id": row[2],
                    "author_name": row[3],
                    "created_at": row[4]
                }
                new_messages.append(message)
                self.last_message_id = max(self.last_message_id, message["id"])
                
            conn.close()
        except Exception as e:
            logger.error(f"Error checking for new messages: {e}")
            
        return new_messages
        
    def _get_active_posts_count(self) -> int:
        """
        Get the count of active (visible) posts.
        
        Returns:
            The number of active posts.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM posts WHERE visible = 1")
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return result[0]
            return 0
        except Exception as e:
            logger.error(f"Error getting active posts count: {e}")
            return 0
            
    def _get_current_metrics(self) -> Dict[str, float]:
        """
        Get the latest values for all metrics.
        
        Returns:
            A dictionary of metric names to values.
        """
        metrics = {}
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get distinct metric names
            cursor.execute("SELECT DISTINCT metric_name FROM metrics")
            metric_names = [row[0] for row in cursor.fetchall()]
            
            # For each metric name, get the latest value
            for name in metric_names:
                cursor.execute(
                    """
                    SELECT metric_value, timestamp FROM metrics 
                    WHERE metric_name = ? 
                    ORDER BY timestamp DESC LIMIT 1
                    """,
                    (name,)
                )
                result = cursor.fetchone()
                if result:
                    metrics[name] = result[0]
                    if name == "active_posts":
                        self.last_metrics_time = result[1]
                    
            conn.close()
        except Exception as e:
            logger.error(f"Error getting current metrics: {e}")
            
        return metrics
        
    def _monitor_loop(self):
        """Main monitoring loop that runs in a background thread."""
        while self.running:
            try:
                # Check for new messages
                new_messages = self._check_new_messages()
                if new_messages:
                    logger.info(f"Found {len(new_messages)} new messages")
                    for callback in self.callbacks:
                        for message in new_messages:
                            callback("new_message", message)
                
                # Get current metrics
                metrics = self._get_current_metrics()
                if metrics:
                    for callback in self.callbacks:
                        callback("metrics_update", metrics)
                
                # Get active posts count
                active_posts = self._get_active_posts_count()
                for callback in self.callbacks:
                    callback("active_posts", active_posts)
                    
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                
            # Sleep for the poll interval
            time.sleep(self.poll_interval)
