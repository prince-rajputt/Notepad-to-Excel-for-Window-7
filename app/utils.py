"""Small shared helpers: datetime formatting, hashing, retry, file-stability waits."""
import hashlib
import os
import time
from datetime import datetime

DATETIME_FORMAT = "%d-%m-%Y %H:%M:%S"

TEMP_PREFIXES = ("~",)
IGNORED_EXTENSIONS = (".tmp", ".temp")


def now_str():
    """Current local time formatted as DD-MM-YYYY HH:MM:SS."""
    return datetime.now().strftime(DATETIME_FORMAT)


def format_datetime(dt):
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.strftime(DATETIME_FORMAT)


def is_temp_or_lock_file(filename):
    """True for editor lock/temp files (~..., .tmp, .temp) that must never be processed."""
    lower = filename.lower()
    if filename.startswith(TEMP_PREFIXES):
        return True
    return any(lower.endswith(ext) for ext in IGNORED_EXTENSIONS)


def is_supported_file(filename, extensions):
    """True for a real, processable file matching one of `extensions` (case-insensitive),
    excluding temp/lock files (~..., .tmp, .temp)."""
    if is_temp_or_lock_file(filename):
        return False
    lower = filename.lower()
    return any(lower.endswith(ext.lower()) for ext in extensions)


def compute_file_hash(file_path, chunk_size=65536):
    """SHA-256 hash of a file's bytes."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def wait_for_stable_file(file_path, checks=5, interval=0.5, timeout=15.0):
    """Wait until a file's size stops changing (i.e. it has finished being copied/saved).

    Returns True once the size has been stable for `checks` consecutive reads,
    False if the file disappeared or the timeout elapsed first.
    """
    deadline = time.time() + timeout
    stable_count = 0
    last_size = -1
    while time.time() < deadline:
        try:
            size = os.path.getsize(file_path)
        except OSError:
            return False
        if size == last_size:
            stable_count += 1
            if stable_count >= checks:
                return True
        else:
            stable_count = 0
            last_size = size
        time.sleep(interval)
    return False


def retry_with_backoff(func, attempts=3, base_delay=1.0, on_retry=None):
    """Call func() with exponential backoff (1s, 2s, 4s, ...) on exception.

    Returns func()'s result on success, or re-raises the last exception after
    exhausting all attempts.
    """
    delay = base_delay
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if on_retry:
                on_retry(attempt, exc)
            if attempt < attempts:
                time.sleep(delay)
                delay *= 2
    raise last_exc
