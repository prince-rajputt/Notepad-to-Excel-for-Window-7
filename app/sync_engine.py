"""Ties together the database, txt reader and excel manager.

Each feed is independent: one source .txt file, one destination workbook.
A feed's workbook is a LIVE MIRROR of its .txt file - on every sync it is
fully rebuilt from the database, which itself only ever holds records for
source files that currently exist on disk (deleting a .txt file hard-deletes
its record and empties its workbook).
"""
import difflib
import logging
import os
import threading

from app.errors import DocumentReadError
from app.excel_manager import (
    ExcelLockedError,
    UnknownFeedFormatError,
    generate_feed_excel,
)
from app.feeds import feed_for_txt_filename
from app.scanner import get_file_stat
from app.txt_reader import extract_hindi_message
from app.utils import compute_file_hash

logger = logging.getLogger("taaza_news_excel_sync")

LINE_PREVIEW_CHARS = 90


def _preview(line):
    line = line.strip()
    return line if len(line) <= LINE_PREVIEW_CHARS else line[:LINE_PREVIEW_CHARS] + "…"


class SyncEngine:
    def __init__(self, db, config):
        self.db = db
        self.config = config
        self._lock = threading.RLock()
        self._pending_excel = set()  # feed keys whose workbook is waiting on a lock
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
    def excel_root(self):
        return self.config.excel_root

    @property
    def feeds(self):
        return self.config.feeds

    @property
    def excel_pending(self):
        """True while at least one workbook is waiting for its file to unlock."""
        return bool(self._pending_excel)

    def is_feed_pending(self, feed_key):
        """True while this specific feed's workbook is waiting for its file to unlock."""
        return feed_key in self._pending_excel

    def feed_for_path(self, full_path):
        """Return the Feed a path belongs to, or None.

        A path only matches if it is directly inside the configured txt_root
        AND its file name is exactly one of the four configured source files -
        every other file and every subfolder is ignored.
        """
        directory = os.path.dirname(os.path.abspath(full_path))
        if os.path.normcase(directory) != os.path.normcase(os.path.abspath(self.txt_root)):
            return None
        return feed_for_txt_filename(os.path.basename(full_path), self.feeds)

    # -- single-feed processing --------------------------------------------------

    def process_feed(self, feed):
        """Create or update the DB record for one feed from its source file.

        Returns the resulting FeedRecord, or None if the source file is
        missing or unreadable - any error is logged and processing continues.
        """
        full_path = self.config.txt_path(feed)
        size, mtime = get_file_stat(full_path)
        if size is None:
            # Missing source file: drop any stale record so the workbook empties.
            self._forget_feed(feed.key, feed.txt_file)
            return None

        with self._lock:
            existing = self.db.get_by_feed_key(feed.key)

            unchanged = (
                existing is not None
                and existing.full_path == full_path
                and existing.size == size
                and existing.mtime == mtime
            )
            if unchanged:
                # Even when the file itself hasn't changed, the feed's label
                # may have been edited - keep it in sync so a config edit is
                # never masked by this fast path.
                if existing.label != feed.label:
                    self.db.update_label(feed.key, feed.label)
                    existing = self.db.get_by_feed_key(feed.key)
                self.db.touch_last_synced(feed.key)
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

            if content_unchanged:
                # metadata changed (e.g. touched) but content identical - avoid reparsing
                return self.db.upsert_feed(
                    feed.key, feed.label, feed.txt_file, full_path,
                    existing.content, file_hash, size, mtime,
                )

            try:
                content = extract_hindi_message(full_path)
            except DocumentReadError as exc:
                logger.error("TXT parsing error for %s: %s", full_path, exc)
                return None

            was_new = existing is None
            news_count = len(content.split("\n")) if content else 0

            record = self.db.upsert_feed(
                feed.key, feed.label, feed.txt_file, full_path, content,
                file_hash, size, mtime,
            )

            if was_new:
                self._notify(f"✓ {feed.txt_file} detected ({feed.label})")
                self._notify(f"✓ {news_count} news items extracted")
                self._notify("✓ BITMAP tags removed")
            else:
                self._notify(f"↻ {feed.txt_file} modified ({feed.label})")
                self._notify_line_diff(existing.content, content)
            return record

    def _forget_feed(self, feed_key, txt_file):
        with self._lock:
            existing = self.db.get_by_feed_key(feed_key)
            if existing:
                self.db.delete_feed(feed_key)
                self._notify(f"✗ {txt_file} deleted")
                self._notify(f"✗ {existing.label} news cleared from its Excel file")

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

    # -- filesystem event handling -------------------------------------------

    def handle_changed(self, full_path):
        """A configured source file was created or modified."""
        feed = self.feed_for_path(full_path)
        if feed is None:
            return None
        record = self.process_feed(feed)
        self.regenerate_feed_excel(feed)
        return record

    handle_created = handle_changed
    handle_modified = handle_changed

    def handle_deleted(self, full_path):
        feed = self.feed_for_path(full_path)
        if feed is None:
            return
        self._forget_feed(feed.key, feed.txt_file)
        self.regenerate_feed_excel(feed)

    def handle_moved(self, src_path, dest_path):
        # A feed's identity is its configured file name, so a rename is just
        # "the old name vanished, the new name appeared" - both sides reuse the
        # normal delete/create handling, and non-feed names are ignored.
        self.handle_deleted(src_path)
        self.handle_changed(dest_path)

    # -- full scan / reconciliation -----------------------------------------------

    def run_full_scan(self, reason="scan", silent=False):
        """Sync every configured feed and purge records for feeds whose source
        file has vanished (or which are no longer configured at all). Used for
        the initial scan on startup, the manual "SYNC NOW" flow, and the
        periodic background safety-net scan (silent=True, so it doesn't spam
        the activity log every few seconds when nothing actually changed).
        """
        if not silent:
            self._notify(f"{reason} started")
        feeds = self.feeds

        for feed in feeds:
            self.process_feed(feed)

        with self._lock:
            configured_keys = {feed.key for feed in feeds}
            for stale_key in self.db.get_all_feed_keys() - configured_keys:
                existing = self.db.get_by_feed_key(stale_key)
                if existing:
                    self.db.delete_feed(stale_key)
                    self._notify(f"✗ {existing.txt_file} is no longer a configured feed")

        for feed in feeds:
            self.regenerate_feed_excel(feed, silent=silent)
        if not silent:
            self._notify(f"{reason} completed")

    def run_initial_scan(self):
        self.run_full_scan(reason="Initial scan")

    def run_reconciliation(self):
        self.run_full_scan(reason="Reconciliation")

    # -- excel ---------------------------------------------------------------

    def regenerate_feed_excel(self, feed, silent=False):
        """Rebuild one feed's workbook from its database record.

        `silent` is set by the periodic background safety-net scan, which
        rewrites every workbook every few seconds purely as a lock-recovery
        check - it did not observe any real change, so it must not announce
        "updated (N rows)" on data that hasn't moved. Recovering from a lock
        and genuine errors are still worth surfacing even when silent.
        """
        record = self.db.get_by_feed_key(feed.key)
        lines = record.news_lines if record else []
        excel_path = self.config.excel_path(feed)
        was_pending = feed.key in self._pending_excel
        try:
            generate_feed_excel(
                feed, lines, excel_path,
                self.config.default_visibility,
                self.config.default_category_time,
                self.config.first_category_time,
                self.config.first_category_count,
            )
            self._pending_excel.discard(feed.key)
            if was_pending:
                self._notify(f"✓ {feed.excel_file} synchronized (file was unlocked)")
            elif not silent:
                self._notify(f"✓ {feed.excel_file} updated ({len(lines)} rows)")
        except ExcelLockedError as exc:
            self._pending_excel.add(feed.key)
            logger.warning("Excel locked, synchronization pending: %s", exc)
            if not was_pending:
                self._notify(f"{feed.excel_file} is open/locked - update pending")
        except UnknownFeedFormatError as exc:
            logger.error("%s", exc)
            self._notify(f"✗ {feed.excel_file} skipped: {exc}")

    def regenerate_all_excel(self):
        for feed in self.feeds:
            self.regenerate_feed_excel(feed)

    def retry_pending_excel(self):
        """Re-attempt only the workbooks that are waiting on a file lock."""
        for feed in self.feeds:
            if feed.key in self._pending_excel:
                self.regenerate_feed_excel(feed)
