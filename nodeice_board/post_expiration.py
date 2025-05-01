import time
import logging
import threading
from datetime import datetime, timedelta
from typing import Optional

from nodeice_board.database import Database


class PostExpirationHandler:
    """
    Handler for expiring old posts after a specified period.
    """
    
    def __init__(self, database: Database, expiration_days: int = 7, check_interval_hours: int = 12):
        """
        Initialize the post expiration handler.
        
        Args:
            database: The database instance.
            expiration_days: Number of days after which posts should be expired (deleted).
            check_interval_hours: How often to check for expired posts (in hours).
        """
        self.db = database
        self.expiration_days = expiration_days
        self.check_interval_seconds = check_interval_hours * 60 * 60
        self.logger = logging.getLogger("NodeiceBoard")
        self.stop_event = threading.Event()
        self.thread = None
    
    def start(self):
        """Start the expiration handler in a background thread."""
        if self.thread and self.thread.is_alive():
            self.logger.warning("Expiration handler already running")
            return
            
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._expiration_loop)
        self.thread.daemon = True
        self.thread.start()
        
        self.logger.info(
            f"Post expiration handler started (will delete posts older than {self.expiration_days} days, "
            f"checking every {self.check_interval_seconds // 3600} hours)"
        )
        
    def stop(self):
        """Stop the expiration handler."""
        if self.thread and self.thread.is_alive():
            self.stop_event.set()
            self.thread.join(timeout=5.0)  # Wait up to 5 seconds for thread to complete
            if self.thread.is_alive():
                self.logger.warning("Expiration handler thread did not terminate cleanly")
            else:
                self.logger.info("Post expiration handler stopped")
        else:
            self.logger.warning("Expiration handler not running")
            
    def _expiration_loop(self):
        """Main loop for the expiration handler."""
        # Run once immediately at startup
        self._delete_expired_posts()
        
        # Then run periodically
        while not self.stop_event.wait(self.check_interval_seconds):
            self._delete_expired_posts()
            
    def _delete_expired_posts(self):
        """Delete posts older than the expiration threshold."""
        try:
            deleted_count = self.db.delete_expired_posts(self.expiration_days)
            if deleted_count > 0:
                self.logger.info(f"Deleted {deleted_count} expired posts")
        except Exception as e:
            self.logger.error(f"Error deleting expired posts: {e}")
