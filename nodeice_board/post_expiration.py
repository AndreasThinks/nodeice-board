import time
import logging
import threading
import traceback
from datetime import datetime, timedelta
from typing import Optional

from nodeice_board.database import Database


class PostExpirationHandler:
    """
    Handler for expiring old posts after a specified period by marking them as not visible.
    """
    
    def __init__(self, database: Database, expiration_days: int = 7, check_interval_hours: int = 12):
        """
        Initialize the post expiration handler.
        
        Args:
            database: The database instance (used only for configuration, not directly accessed from thread).
            expiration_days: Number of days after which posts should be marked as not visible.
            check_interval_hours: How often to check for expired posts (in hours).
        """
        # Store the database path rather than the database instance
        self.db_path = database.db_path
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
            f"Post expiration handler started (will mark posts older than {self.expiration_days} days as not visible, "
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
        self._mark_expired_posts_as_invisible()
        
        # Then run periodically
        while not self.stop_event.wait(self.check_interval_seconds):
            self._mark_expired_posts_as_invisible()
            
    def _mark_expired_posts_as_invisible(self):
        """Mark posts older than the expiration threshold as not visible."""
        # Create a new database connection in this thread
        thread_db = None
        try:
            thread_db = Database(self.db_path)
            updated_count = thread_db.mark_expired_posts_as_invisible(self.expiration_days)
            if updated_count > 0:
                self.logger.info(f"Marked {updated_count} expired posts as not visible")
        except Exception as e:
            self.logger.error(f"Error marking expired posts as not visible: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            # Close the database connection
            if thread_db:
                thread_db.close()
