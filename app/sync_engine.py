"""Ties together the scanner, database, txt reader and excel manager.

The row number parsed from a filename is the file's permanent identity.
The Excel workbook is a LIVE MIRROR of the currently-existing row_XX.txt
files: on every sync, News Data is fully rebuilt from the database, which
itself only ever contains records for files that currently exist on disk
(deleting a file hard-deletes its database record).
"""
import difflib
import logging
import os
import threading

from app.errors import DocumentReadError
from app.excel_manager import ExcelLockedError, generate_excel
from app.row_mapping import category_for_row, is_row_enabled, parse_row_number
from app.scanner import get_file_stat, list_target_files
from app.txt_reader import extract_hindi_message
from app.utils import compute_file_hash, is_supported_file

logger = logging.getLogger("word_to_excel_sync")

LINE_PREVIEW_CHARS = 90


def _preview(line):
    line = line.strip()
    return line if len(line) <= LINE_PREVIEW_CHARS else line[:LINE_PREVIEW_CHARS] + "…"


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

        if not is_row_enabled(row_number, self.config):
            logger.debug("Skipping disabled row %s (%s): not in row_categories", row_number, filename)
            return None

        size, mtime = get_file_stat(full_path)
        if size is None:
            logger.warning("File disappeared before it could be processed: %s", full_path)
            return None

        with self._lock:
            existing = self.db.get_by_row_number(row_number)

            unchanged = (
                existing is not None
                and existing.full_path == full_path
                and existing.size == size
                and existing.mtime == mtime
            )
            if unchanged:
                # Even when the file itself hasn't changed, the row_categories
                # mapping in config.json may have - always re-sync the category
                # so a config edit is never masked by this fast path.
                current_category = category_for_row(row_number, self.config)
                if existing.category != current_category:
                    self.db.update_category(row_number, current_category)
                    existing = self.db.get_by_row_number(row_number)
                self.db.touch_last_synced(row_number)
                return existing

            try:
                file_hash = compute_file_hash(full_path)
            except OSError as exc:
                logger.error("Could not hash file %s: %s", full_path, exc)
                return None

            content_unchanged = (
                existing is not None
                and existing.full_path == full_path
                and existing.file_hash == file_hash
            )
            category = category_for_row(row_number, self.config)

            if content_unchanged:
                # metadata changed (e.g. touched) but content identical - avoid reparsing
                return self.db.upsert_row(
                    row_number, category, filename, full_path,
                    existing.content, file_hash, size, mtime,
                )

            try:
                content = extract_hindi_message(full_path)
            except DocumentReadError as exc:
                logger.error("TXT parsing error for %s: %s", full_path, exc)
                return None

            was_new = existing is None
            news_count = len(content.split("\n")) if content else 0

            record = self.db.upsert_row(
                row_number, category, filename, full_path, content, file_hash, size, mtime
            )

            if was_new:
                self._notify(f"✓ {filename} detected")
                self._notify(f"✓ {category} processed")
                self._notify(f"✓ {news_count} Hindi news items extracted")
                self._notify("✓ BITMAP tags removed")
            else:
                self._notify(f"↻ {filename} modified")
                self._notify(f"↻ {category} refreshed")
                self._notify_line_diff(existing.content, content)
            return record

    def _notify_line_diff(self, old_content, new_content):
        """Emit one activity-log line per changed news line, so the user can see
        exactly which line was added, removed, or edited - not just that the
        file as a whole changed."""
        old_lines = old_content.split("\n") if old_content else []
        new_lines = new_content.split("\n") if new_content else []
        matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            if tag == "replace" and (i2 - i1) == (j2 - j1):
                for old_line, new_line in zip(old_lines[i1:i2], new_lines[j1:j2]):
                    self._notify(f"~ line edited: \"{_preview(old_line)}\" → \"{_preview(new_line)}\"")
            else:
                for old_line in old_lines[i1:i2]:
                    self._notify(f"− line removed: \"{_preview(old_line)}\"")
                for new_line in new_lines[j1:j2]:
                    self._notify(f"+ line added: \"{_preview(new_line)}\"")

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
                if existing:
                    self.db.delete_row(row_number)
                    self._notify(f"✗ {filename} deleted")
                    self._notify(f"✗ {existing.category} news removed from current Excel")
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
        """Scan the root folder, sync every row_XX.txt file, and remove records for
        rows whose file has vanished. Used for both the initial scan on startup and
        the manual "SYNC NOW" / reconciliation flow - the logic is identical.
        """
        self._notify(f"{reason} started")
        current_paths = list_target_files(self.txt_root, self.watch_extensions)

        current_row_numbers = set()
        for path in current_paths:
            row_number = parse_row_number(os.path.basename(path))
            if row_number is not None and is_row_enabled(row_number, self.config):
                current_row_numbers.add(row_number)
            self.process_file(path)

        with self._lock:
            # Anything tracked that is no longer both present-on-disk AND enabled
            # (file deleted, or its row was removed from the mapping) is purged -
            # Excel must never show a row number outside the current whitelist.
            tracked_row_numbers = self.db.get_all_row_numbers()
            missing_row_numbers = tracked_row_numbers - current_row_numbers
            for row_number in missing_row_numbers:
                existing = self.db.get_by_row_number(row_number)
                if existing:
                    self.db.delete_row(row_number)
                    self._notify(f"✗ {existing.file_name} deleted")
                    self._notify(f"✗ {existing.category} news removed from current Excel")

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
            generate_excel(records, self.excel_file, self.config.row_categories)
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
