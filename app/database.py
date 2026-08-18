"""SQLite persistence layer - internal cache of the currently-existing row_XX.txt
files, keyed by row number.

There is no soft-delete: when a row_XX.txt file disappears from the folder,
its record is removed entirely. The database always reflects exactly the set
of files currently on disk (used to avoid unnecessary re-parsing of unchanged
files); the Excel workbook is regenerated from this table as a live mirror.
"""
import logging
import sqlite3
import threading

from app.models import FileRecord
from app.utils import now_str

logger = logging.getLogger("word_to_excel_sync")

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    row_number INTEGER NOT NULL UNIQUE,
    category TEXT NOT NULL DEFAULT 'Unassigned',
    file_name TEXT NOT NULL,
    full_path TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    file_hash TEXT NOT NULL DEFAULT '',
    size INTEGER NOT NULL DEFAULT 0,
    mtime REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    modified_at TEXT NOT NULL,
    last_synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_files_row_number ON files(row_number);
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

    def get_by_row_number(self, row_number):
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM files WHERE row_number = ?", (row_number,)
            ).fetchone()
        return FileRecord.from_row(row) if row else None

    def get_all(self):
        with self._lock:
            rows = self._conn.execute("SELECT * FROM files ORDER BY row_number ASC").fetchall()
        return [FileRecord.from_row(r) for r in rows]

    def get_all_row_numbers(self):
        with self._lock:
            rows = self._conn.execute("SELECT row_number FROM files").fetchall()
        return {r["row_number"] for r in rows}

    def search(self, query_text):
        query = "SELECT * FROM files WHERE (category LIKE ? OR file_name LIKE ?) ORDER BY row_number ASC"
        like = f"%{query_text}%"
        with self._lock:
            rows = self._conn.execute(query, (like, like)).fetchall()
        return [FileRecord.from_row(r) for r in rows]

    # -- mutations -----------------------------------------------------------

    def upsert_row(self, row_number, category, file_name, full_path, content, file_hash, size, mtime):
        """Create a new record for a never-before-seen row number, or update the
        existing one in place (a file modification)."""
        timestamp = now_str()
        with self._lock:
            existing = self._conn.execute(
                "SELECT id FROM files WHERE row_number = ?", (row_number,)
            ).fetchone()

            if existing is None:
                self._conn.execute(
                    """
                    INSERT INTO files (
                        row_number, category, file_name, full_path, content,
                        file_hash, size, mtime, created_at, modified_at, last_synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row_number, category, file_name, full_path, content,
                        file_hash, size, mtime, timestamp, timestamp, timestamp,
                    ),
                )
                logger.info("New row record: row_number=%s -> %s", row_number, full_path)
            else:
                self._conn.execute(
                    """
                    UPDATE files
                    SET category = ?, file_name = ?, full_path = ?, content = ?,
                        file_hash = ?, size = ?, mtime = ?, modified_at = ?,
                        last_synced_at = ?
                    WHERE row_number = ?
                    """,
                    (
                        category, file_name, full_path, content, file_hash, size,
                        mtime, timestamp, timestamp, row_number,
                    ),
                )
                logger.info("Updated row record: row_number=%s", row_number)
            self._conn.commit()
        return self.get_by_row_number(row_number)

    def touch_last_synced(self, row_number):
        timestamp = now_str()
        with self._lock:
            self._conn.execute(
                "UPDATE files SET last_synced_at = ? WHERE row_number = ?",
                (timestamp, row_number),
            )
            self._conn.commit()

    def delete_row(self, row_number):
        """Hard-delete a record - the Excel News Data sheet must not show news
        for a row_XX.txt file that no longer exists (live-mirror requirement)."""
        with self._lock:
            self._conn.execute("DELETE FROM files WHERE row_number = ?", (row_number,))
            self._conn.commit()
        logger.info("Deleted row record: row_number=%s", row_number)

    def update_category(self, row_number, category):
        with self._lock:
            self._conn.execute(
                "UPDATE files SET category = ? WHERE row_number = ?", (category, row_number)
            )
            self._conn.commit()

    def refresh_categories(self, category_lookup):
        """Bulk-update every record's category from a row_number -> category lookup
        function. Used when the user edits the Row/Category Mapping in the GUI so
        existing Excel rows reflect the new names immediately."""
        with self._lock:
            rows = self._conn.execute("SELECT row_number FROM files").fetchall()
            for row in rows:
                row_number = row["row_number"]
                category = category_lookup(row_number)
                self._conn.execute(
                    "UPDATE files SET category = ? WHERE row_number = ?", (category, row_number)
                )
            self._conn.commit()

    def stats(self):
        with self._lock:
            rows = self._conn.execute("SELECT content FROM files").fetchall()
        total_files = len(rows)
        news_items = sum(len(r["content"].split("\n")) if r["content"] else 0 for r in rows)
        return {"total_files": total_files, "news_items": news_items, "active_categories": total_files}
