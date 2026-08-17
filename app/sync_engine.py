"""Ties together the scanner, database, txt reader and excel manager.

This is the single place that implements the row_XX.txt create/modify/delete/
recreate synchronization rules described in the specification. The row
number parsed from a filename is the file's permanent identity: "modify" and
"recreate" both boil down to the same upsert-by-row-number operation.
"""
import logging
import os
import threading

from app.errors import DocumentReadError
from app.excel_manager import ExcelLockedError, generate_excel
from app.row_mapping import category_for_row, parse_row_number
from app.scanner import get_file_stat, list_target_files
from app.txt_reader import extract_hindi_message
from app.utils import compute_file_hash, is_supported_file

logger = logging.getLogger("word_to_excel_sync")


class SyncEngine:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self._lock = threading.RLock()
        self.excel_pending = False
        self.on_event = None  # optional callback(message: str) for GUI activity log

    def _notify(self, message):
        logger.info(message)
        if self.on_event:
            try:
                self.on_event(message)
            except Exception:  # noqa: BLE001 - GUI callbacks must never break sync
                logger.exception("Activity log callback failed")

    @property
    def txt_root(self):
        return self.config.txt_root

    @property
    def excel_file(self):
        return self.config.excel_file

    @property
    def watch_extensions(self):
        return self.config.get("watch_extensions", [".txt"])

    # -- single-file processing --------------------------------------------------

    def process_file(self, full_path):
        """Create or update the DB record for one row_XX.txt file based on its
        current content.

        Returns the resulting FileRecord, or None if the file could not be
        processed (missing, unreadable, or its filename doesn't match the
        row_XX.txt pattern) - any error is logged and processing continues.
        """
        filename = os.path.basename(full_path)
        if not is_supported_file(filename, self.watch_extensions):
            return None

        row_number = parse_row_number(filename)
        if row_number is None:
            logger.warning("Skipping non-row TXT file (expected row_XX.txt): %s", filename)
            return None

        size, mtime = get_file_stat(full_path)
        if size is None:
            logger.warning("File disappeared before it could be processed: %s", full_path)
            return None

        with self._lock:
            existing = self.db.get_by_row_number(row_number)

            unchanged_active_file = (
                existing is not None
                and existing.status == "Active"
                and existing.full_path == full_path
                and existing.size == size
                and existing.mtime == mtime
            )
            if unchanged_active_file:
                self.db.touch_last_synced(row_number)
                return existing

            try:
                file_hash = compute_file_hash(full_path)
            except OSError as exc:
                logger.error("Could not hash file %s: %s", full_path, exc)
                return None

            content_unchanged = (
                existing is not None
                and existing.status == "Active"
                and existing.full_path == full_path
                and existing.file_hash == file_hash
            )
            category = category_for_row(row_number, self.config)

            if content_unchanged:
                # metadata changed (e.g. touched) but content identical - avoid reparsing
                record = self.db.upsert_row(
                    row_number, category, filename, full_path,
                    existing.content, file_hash, size, mtime,
                )
                return record

            try:
                content = extract_hindi_message(full_path)
            except DocumentReadError as exc:
                logger.error("TXT parsing error for %s: %s", full_path, exc)
                return None

            was_new = existing is None
            was_deleted = existing is not None and existing.status == "Deleted"

            record = self.db.upsert_row(
                row_number, category, filename, full_path, content, file_hash, size, mtime
            )

            if was_new:
                self._notify(f"+ {filename} added")
            elif was_deleted:
                self._notify(f"↻ {filename} recreated")
            else:
                self._notify(f"↻ {filename} modified")
            return record

    def handle_created(self, full_path):
        record = self.process_file(full_path)
        self.regenerate_excel()
        return record

    def handle_modified(self, full_path):
        record = self.process_file(full_path)
        self.regenerate_excel()
        return record

    def handle_deleted(self, full_path):
        filename = os.path.basename(full_path)
        row_number = parse_row_number(filename)
        if row_number is not None:
            with self._lock:
                existing = self.db.get_by_row_number(row_number)
                if existing and existing.status == "Active":
                    self.db.mark_deleted(row_number)
                    self._notify(f"✗ {filename} deleted")
        self.regenerate_excel()

    def handle_moved(self, src_path, dest_path):
        # Identity is derived purely from the row_XX.txt filename pattern, so a
        # rename/move is just "the old path's row is gone, the new path's row
        # appeared" - both cases reuse the existing create/delete handling.
        self.handle_deleted(src_path)
        self.process_file(dest_path)
        self.regenerate_excel()

    # -- full scan / reconciliation -----------------------------------------------

    def run_full_scan(self, reason="scan"):
        """Scan the root folder, sync every row_XX.txt file, and mark vanished
        rows as Deleted. Used for both the initial scan on startup and the
        manual "SYNC NOW" / reconciliation flow - the logic is identical.
        """
        self._notify(f"{reason} started")
        current_paths = list_target_files(self.txt_root, self.watch_extensions)

        current_row_numbers = set()
        for path in current_paths:
            row_number = parse_row_number(os.path.basename(path))
            if row_number is not None:
                current_row_numbers.add(row_number)
            self.process_file(path)

        with self._lock:
            active_row_numbers = self.db.get_active_row_numbers()
            missing_row_numbers = active_row_numbers - current_row_numbers
            for row_number in missing_row_numbers:
                existing = self.db.get_by_row_number(row_number)
                if existing:
                    self.db.mark_deleted(row_number)
                    self._notify(f"✗ {existing.file_name} deleted")

        self.regenerate_excel()
        self._notify(f"{reason} completed")

    def run_initial_scan(self):
        self.run_full_scan(reason="Initial scan")

    def run_reconciliation(self):
        self.run_full_scan(reason="Reconciliation")

    # -- category mapping -----------------------------------------------------

    def refresh_categories(self):
        """Re-apply the current config row/category mapping to every existing
        record (used after the user edits the Row/Category Mapping panel), and
        regenerate Excel so the change is visible immediately."""
        self.db.refresh_categories(lambda row_number: category_for_row(row_number, self.config))
        self.regenerate_excel()
        self._notify("Row/Category mapping updated")

    # -- excel ---------------------------------------------------------------

    def regenerate_excel(self):
        was_pending = self.excel_pending
        records = self.db.get_all()
        try:
            generate_excel(records, self.excel_file)
            self.excel_pending = False
            if was_pending:
                self._notify("✓ Excel synchronized (file was unlocked)")
            else:
                self._notify("✓ Excel updated")
        except ExcelLockedError as exc:
            self.excel_pending = True
            logger.warning("Excel locked, synchronization pending: %s", exc)
            if not was_pending:
                self._notify("Excel file is open/locked - update pending")
