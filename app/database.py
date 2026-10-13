"""SQLite persistence layer - internal cache of the currently-existing feed
source files, keyed by feed key.

There is no soft-delete: when a feed's .txt file disappears from the folder,
its record is removed entirely. The database always reflects exactly the set
of feed files currently on disk (used to avoid unnecessary re-parsing of
unchanged files); each workbook is regenerated from this table as a live
mirror of its own feed.
"""
import logging
import sqlite3
import threading

from app.models import FeedRecord
from app.utils import now_str

logger = logging.getLogger("taaza_news_excel_sync")

SCHEMA = """
CREATE TABLE IF NOT EXISTS feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_key TEXT NOT NULL UNIQUE,
    label TEXT NOT NULL DEFAULT '',
    txt_file TEXT NOT NULL,
    full_path TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    file_hash TEXT NOT NULL DEFAULT '',
    size INTEGER NOT NULL DEFAULT 0,
    mtime REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    modified_at TEXT NOT NULL,
    last_synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_feeds_feed_key ON feeds(feed_key);
"""


class Database:
    """Thread-safe wrapper around the sync.db SQLite database."""

    def __init__(self, db_path):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()

    # -- queries -----------------------------------------------------------

    def get_by_feed_key(self, feed_key):
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM feeds WHERE feed_key = ?", (feed_key,)
            ).fetchone()
        return FeedRecord.from_row(row) if row else None

    def get_all(self):
        with self._lock:
            rows = self._conn.execute("SELECT * FROM feeds ORDER BY id ASC").fetchall()
        return [FeedRecord.from_row(r) for r in rows]

    def get_all_feed_keys(self):
        with self._lock:
            rows = self._conn.execute("SELECT feed_key FROM feeds").fetchall()
        return {r["feed_key"] for r in rows}

    def search(self, query_text):
        query = (
            "SELECT * FROM feeds WHERE (label LIKE ? OR txt_file LIKE ? OR feed_key LIKE ?) "
            "ORDER BY id ASC"
        )
        like = f"%{query_text}%"
        with self._lock:
            rows = self._conn.execute(query, (like, like, like)).fetchall()
        return [FeedRecord.from_row(r) for r in rows]

    # -- mutations -----------------------------------------------------------

    def upsert_feed(self, feed_key, label, txt_file, full_path, content, file_hash, size, mtime):
        """Create a new record for a never-before-seen feed, or update the
        existing one in place (a source file modification)."""
        timestamp = now_str()
        with self._lock:
            existing = self._conn.execute(
                "SELECT id FROM feeds WHERE feed_key = ?", (feed_key,)
            ).fetchone()

            if existing is None:
                self._conn.execute(
                    """
                    INSERT INTO feeds (
                        feed_key, label, txt_file, full_path, content,
                        file_hash, size, mtime, created_at, modified_at, last_synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        feed_key, label, txt_file, full_path, content,
                        file_hash, size, mtime, timestamp, timestamp, timestamp,
                    ),
                )
                logger.info("New feed record: %s -> %s", feed_key, full_path)
            else:
                self._conn.execute(
                    """
                    UPDATE feeds
                    SET label = ?, txt_file = ?, full_path = ?, content = ?,
                        file_hash = ?, size = ?, mtime = ?, modified_at = ?,
                        last_synced_at = ?
                    WHERE feed_key = ?
                    """,
                    (
                        label, txt_file, full_path, content, file_hash, size,
                        mtime, timestamp, timestamp, feed_key,
                    ),
                )
                logger.info("Updated feed record: %s", feed_key)
            self._conn.commit()
        return self.get_by_feed_key(feed_key)

    def touch_last_synced(self, feed_key):
        timestamp = now_str()
        with self._lock:
            self._conn.execute(
                "UPDATE feeds SET last_synced_at = ? WHERE feed_key = ?",
                (timestamp, feed_key),
            )
            self._conn.commit()

    def delete_feed(self, feed_key):
        """Hard-delete a record - a feed's workbook must not show news for a
        .txt file that no longer exists (live-mirror requirement)."""
        with self._lock:
            self._conn.execute("DELETE FROM feeds WHERE feed_key = ?", (feed_key,))
            self._conn.commit()
        logger.info("Deleted feed record: %s", feed_key)

    def update_label(self, feed_key, label):
        with self._lock:
            self._conn.execute(
                "UPDATE feeds SET label = ? WHERE feed_key = ?", (label, feed_key)
            )
            self._conn.commit()

    def stats(self):
        with self._lock:
            rows = self._conn.execute("SELECT content FROM feeds").fetchall()
        total_files = len(rows)
        news_items = sum(len(r["content"].split("\n")) if r["content"] else 0 for r in rows)
        return {"total_files": total_files, "news_items": news_items}
