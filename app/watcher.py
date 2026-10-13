"""Real-time folder monitoring using watchdog, with debouncing and copy-stability checks."""
import logging
import os
import threading

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.utils import wait_for_stable_file

logger = logging.getLogger("taaza_news_excel_sync")

DEBOUNCE_SECONDS = 1.5


class _DebouncedHandler(FileSystemEventHandler):
    """Coalesces the burst of create/modify events one Notepad save typically
    produces, waits for the file to finish being written, then hands it to the
    sync engine.

    Every event is filtered through engine.feed_for_path() first, so only the
    configured source files trigger any work - the rest of the folder's
    contents are ignored no matter how often they change.
    """

    def __init__(self, engine, debounce_seconds=DEBOUNCE_SECONDS):
        self.engine = engine
        self.debounce_seconds = debounce_seconds
        self._timers = {}
        self._lock = threading.Lock()

    def _is_feed_path(self, path):
        return self.engine.feed_for_path(path) is not None

    def on_created(self, event):
        if event.is_directory:
            return
        self._schedule(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        self._schedule(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        if not self._is_feed_path(event.src_path):
            return
        self._cancel(event.src_path)
        try:
            self.engine.handle_deleted(event.src_path)
        except Exception:  # noqa: BLE001 - one bad event must not kill the watcher thread
            logger.exception("Watcher error handling delete: %s", event.src_path)

    def on_moved(self, event):
        if event.is_directory:
            return
        self._cancel(event.src_path)
        if not self._is_feed_path(event.src_path) and not self._is_feed_path(event.dest_path):
            return
        try:
            self.engine.handle_moved(event.src_path, event.dest_path)
        except Exception:  # noqa: BLE001
            logger.exception(
                "Watcher error handling move: %s -> %s", event.src_path, event.dest_path
            )

    def _schedule(self, path):
        if not self._is_feed_path(path):
            return
        with self._lock:
            existing = self._timers.get(path)
            if existing:
                existing.cancel()
            timer = threading.Timer(self.debounce_seconds, self._process, args=(path,))
            timer.daemon = True
            self._timers[path] = timer
            timer.start()

    def _cancel(self, path):
        with self._lock:
            existing = self._timers.pop(path, None)
        if existing:
            existing.cancel()

    def _process(self, path):
        with self._lock:
            self._timers.pop(path, None)

        if not os.path.exists(path):
            return  # deleted before the debounce window elapsed; on_deleted already handled it

        if not wait_for_stable_file(path):
            logger.warning("File did not stabilize before processing, proceeding anyway: %s", path)

        try:
            self.engine.handle_changed(path)
        except Exception:  # noqa: BLE001
            logger.exception("Watcher error processing file: %s", path)


class FolderWatcher:
    """Wraps a watchdog Observer scoped to a single non-recursive root folder."""

    def __init__(self, engine, debounce_seconds=DEBOUNCE_SECONDS):
        self.engine = engine
        self.handler = _DebouncedHandler(engine, debounce_seconds)
        self._observer = None

    def start(self):
        if self.is_running():
            return
        root = self.engine.txt_root
        if not os.path.isdir(root):
            raise FileNotFoundError(f"TXT folder does not exist: {root}")
        self._observer = Observer()
        self._observer.schedule(self.handler, root, recursive=False)
        self._observer.start()
        logger.info("Watcher started on %s", root)

    def stop(self):
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            logger.info("Watcher stopped")

    def is_running(self):
        return self._observer is not None and self._observer.is_alive()
