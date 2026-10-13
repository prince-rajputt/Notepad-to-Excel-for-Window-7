"""Named-mutex guard so only one copy of the app runs at a time.

Two instances would both rebuild the same four workbooks from their own
database, overwriting each other's output in the live Excel folder. A Windows
named mutex is the cheapest reliable guard: the kernel releases it
automatically when the process dies, so a crash can never leave a stale lock
behind (unlike a lock file).

The mutex name is app-specific, so the older single-workbook app is unaffected
and both can still run side by side.
"""
import ctypes
import logging
import sys

logger = logging.getLogger("taaza_news_excel_sync")

MUTEX_NAME = "Local\\TaazaNewsExcelSync_SingleInstance"
_ERROR_ALREADY_EXISTS = 183


class SingleInstance:
    """Holds the mutex for the lifetime of the process.

    Keep a reference to the instance for as long as the app runs - letting it
    be garbage-collected releases the handle.
    """

    def __init__(self, name=MUTEX_NAME):
        self.name = name
        self._handle = None
        self.already_running = False

        if sys.platform != "win32":
            return  # no guard off Windows; the app is Windows-only anyway

        try:
            self._handle = ctypes.windll.kernel32.CreateMutexW(None, False, name)
            self.already_running = (
                ctypes.windll.kernel32.GetLastError() == _ERROR_ALREADY_EXISTS
            )
        except (AttributeError, OSError) as exc:
            # If the guard itself cannot be created, fail open rather than
            # blocking the user from running the app at all.
            logger.warning("Could not create single-instance mutex: %s", exc)

    def release(self):
        if self._handle:
            try:
                ctypes.windll.kernel32.CloseHandle(self._handle)
            except (AttributeError, OSError):
                pass
            self._handle = None
