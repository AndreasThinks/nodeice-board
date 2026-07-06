"""
Read-only watcher for the Nodeice Board database.

Runs in a background thread, polls the SQLite database the main
application writes to, and pushes events onto a queue for the display's
render loop. The connection is opened in read-only mode so the display
process can never corrupt or lock out the notice board itself.
"""

import os
import queue
import sqlite3
import logging
import threading
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("NodeiceMatrix")


@dataclass
class Stats:
    """Periodic snapshot of board statistics."""
    visible_posts: int
    total_posts: int


@dataclass
class NewPost:
    """A post created since the watcher started."""
    post_id: int
    content: str
    author: str


@dataclass
class NewComment:
    """A comment created since the watcher started."""
    post_id: int
    content: str
    author: str


@dataclass
class RecentPosts:
    """The most recent visible posts, for the ticker."""
    posts: List[NewPost] = field(default_factory=list)


@dataclass
class DbStatus:
    """Whether the database is currently reachable."""
    available: bool


class BoardWatcher(threading.Thread):
    """Polls the board database and emits events onto a queue."""

    def __init__(self, db_path: str, events: "queue.Queue", poll_interval: float = 2.0):
        """
        Args:
            db_path: Path to the Nodeice Board SQLite database.
            events: Queue that events are pushed onto.
            poll_interval: Seconds between polls.
        """
        super().__init__(name="BoardWatcher", daemon=True)
        self.db_path = db_path
        self.events = events
        self.poll_interval = poll_interval
        self.stop_event = threading.Event()

        self._conn: Optional[sqlite3.Connection] = None
        self._last_post_id: Optional[int] = None
        self._last_comment_id: Optional[int] = None
        self._db_available: Optional[bool] = None  # Unknown until first poll

    # -- Connection handling -------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        # mode=ro guarantees we cannot write; it also fails cleanly if the
        # database file does not exist yet.
        uri = f"file:{self.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        return conn

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = self._connect()
        return self._conn

    def _drop_conn(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def _set_db_available(self, available: bool):
        if available != self._db_available:
            self._db_available = available
            self.events.put(DbStatus(available=available))
            if available:
                logger.info("Board database is reachable")
            else:
                logger.warning(f"Board database not reachable at {self.db_path}")

    # -- Polling -------------------------------------------------------------

    def _poll_once(self):
        if not os.path.exists(self.db_path):
            self._drop_conn()
            self._set_db_available(False)
            return

        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            max_post_id = cursor.execute("SELECT COALESCE(MAX(id), 0) FROM posts").fetchone()[0]
            max_comment_id = cursor.execute("SELECT COALESCE(MAX(id), 0) FROM comments").fetchone()[0]

            first_poll = self._last_post_id is None
            if first_poll:
                # Don't replay history on startup; start from the current state
                self._last_post_id = max_post_id
                self._last_comment_id = max_comment_id

            # New posts since last poll (cap the batch so a burst doesn't
            # monopolise the display)
            if max_post_id > self._last_post_id:
                rows = cursor.execute(
                    "SELECT id, content, author_name, author_id FROM posts "
                    "WHERE id > ? AND visible = 1 ORDER BY id LIMIT 5",
                    (self._last_post_id,),
                ).fetchall()
                for post_id, content, author_name, author_id in rows:
                    self.events.put(NewPost(
                        post_id=post_id,
                        content=content,
                        author=author_name or author_id,
                    ))
                self._last_post_id = max_post_id

            # New comments since last poll
            if max_comment_id > self._last_comment_id:
                rows = cursor.execute(
                    "SELECT id, post_id, content, author_name, author_id FROM comments "
                    "WHERE id > ? ORDER BY id LIMIT 5",
                    (self._last_comment_id,),
                ).fetchall()
                for _comment_id, post_id, content, author_name, author_id in rows:
                    self.events.put(NewComment(
                        post_id=post_id,
                        content=content,
                        author=author_name or author_id,
                    ))
                self._last_comment_id = max_comment_id

            visible = cursor.execute("SELECT COUNT(*) FROM posts WHERE visible = 1").fetchone()[0]
            total = cursor.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
            self.events.put(Stats(visible_posts=visible, total_posts=total))

            recent = cursor.execute(
                "SELECT id, content, author_name, author_id FROM posts "
                "WHERE visible = 1 ORDER BY id DESC LIMIT 3"
            ).fetchall()
            self.events.put(RecentPosts(posts=[
                NewPost(post_id=r[0], content=r[1], author=r[2] or r[3]) for r in recent
            ]))

            self._set_db_available(True)
        except sqlite3.Error as e:
            # Transient lock/IO errors: drop the connection and retry next poll
            logger.warning(f"Database poll failed: {e}")
            self._drop_conn()
            self._set_db_available(False)

    def run(self):
        logger.info(f"Board watcher started, polling {self.db_path} every {self.poll_interval}s")
        # Poll immediately, then on the interval
        self._poll_once()
        while not self.stop_event.wait(self.poll_interval):
            self._poll_once()
        self._drop_conn()
        logger.info("Board watcher stopped")

    def stop(self):
        self.stop_event.set()
