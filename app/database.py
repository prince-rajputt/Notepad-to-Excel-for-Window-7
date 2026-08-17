"""SQLite persistence layer - the source of truth for tracked row_XX.txt files.

The row number parsed from the filename (row_XX.txt -> XX) is the permanent
identity AND the Excel serial number for a record: it never changes, and a
"recreated" file with the same row number reuses (updates in place) the same
database row rather than creating a new one.
"""
import logging
import sqlite3
import threading

from app.models import FileRecord, STATUS_ACTIVE, STATUS_DELETED
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
    deleted_at TEXT,
    status TEXT NOT NULL DEFAULT 'Active',
    last_synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_files_row_number ON files(row_number);
CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
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

    def get_all(self, status=None):
        query = "SELECT * FROM files"
        params = []
        if status and status != "All":
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY row_number ASC"
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [FileRecord.from_row(r) for r in rows]

    def get_active_row_numbers(self):
        with self._lock:
            rows = self._conn.execute(
                "SELECT row_number FROM files WHERE status = ?", (STATUS_ACTIVE,)
            ).fetchall()
        return {r["row_number"] for r in rows}

    def search(self, query_text, status=None):
        query = "SELECT * FROM files WHERE (category LIKE ? OR file_name LIKE ?)"
        like = f"%{query_text}%"
        params = [like, like]
        if status and status != "All":
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY row_number ASC"
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [FileRecord.from_row(r) for r in rows]

    # -- mutations -----------------------------------------------------------

    def upsert_row(self, row_number, category, file_name, full_path, content, file_hash, size, mtime):
        """Create a new record for a never-before-seen row number, or update the
        existing one in place (reactivating it if it had been marked Deleted).
        This single operation implements both "modify" and "recreate" from the
        spec: the row number is the permanent key, so both cases are the same
        thing - write the current file state into the row's one and only record.
        """
        timestamp = now_str()
        with self._lock:
            existing = self._conn.execute(
                "SELECT id, created_at FROM files WHERE row_number = ?", (row_number,)
            ).fetchone()

            if existing is None:
                self._conn.execute(
                    """
                    INSERT INTO files (
                        row_number, category, file_name, full_path, content,
                        file_hash, size, mtime, created_at, modified_at, deleted_at,
                        status, last_synced_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                    """,
                    (
                        row_number, category, file_name, full_path, content,
                        file_hash, size, mtime, timestamp, timestamp,
                        STATUS_ACTIVE, timestamp,
                    ),
                )
                logger.info("New row record: row_number=%s -> %s", row_number, full_path)
            else:
                self._conn.execute(
                    """
                    UPDATE files
                    SET category = ?, file_name = ?, full_path = ?, content = ?,
                        file_hash = ?, size = ?, mtime = ?, modified_at = ?,
                        deleted_at = NULL, status = ?, last_synced_at = ?
                    WHERE row_number = ?
                    """,
                    (
                        category, file_name, full_path, content, file_hash, size,
                        mtime, timestamp, STATUS_ACTIVE, timestamp, row_number,
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

    def mark_deleted(self, row_number):
        timestamp = now_str()
        with self._lock:
            self._conn.execute(
                """
                UPDATE files
                SET status = ?, deleted_at = ?, last_synced_at = ?
                WHERE row_number = ?
                """,
                (STATUS_DELETED, timestamp, timestamp, row_number),
            )
            self._conn.commit()
        logger.info("Marked deleted row_number=%s", row_number)
        return self.get_by_row_number(row_number)

    def update_category(self, row_number, category):
        with self._lock:
            self._conn.execute(
                "UPDATE files SET category = ? WHERE row_number = ?", (category, row_number)
            )
            self._conn.commit()

    def refresh_categories(self, category_lookup):
        """Bulk-update every record's category from a {row_number: category} dict.
        Used when the user edits the Row/Category Mapping in the GUI so existing
        Excel rows reflect the new names immediately, without touching any file."""
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
            total = self._conn.execute("SELECT COUNT(*) AS c FROM files").fetchone()["c"]
            active = self._conn.execute(
                "SELECT COUNT(*) AS c FROM files WHERE status = ?", (STATUS_ACTIVE,)
            ).fetchone()["c"]
            deleted = self._conn.execute(
                "SELECT COUNT(*) AS c FROM files WHERE status = ?", (STATUS_DELETED,)
            ).fetchone()["c"]
        return {"total": total, "active": active, "deleted": deleted}
