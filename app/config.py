"""Load/save config.json."""
import copy
import json
import logging
import os

from app.feeds import (
    DEFAULT_CATEGORY_TIME,
    DEFAULT_FEEDS,
    DEFAULT_FIRST_CATEGORY_COUNT,
    DEFAULT_FIRST_CATEGORY_TIME,
    DEFAULT_VISIBILITY,
    load_feeds,
)

DEFAULT_TXT_ROOT = os.path.join(os.path.expanduser("~"), "Documents", "notepad")
DEFAULT_EXCEL_ROOT = os.path.join(os.path.expanduser("~"), "Desktop", "Excel taza tv")

DEFAULT_CONFIG = {
    "txt_root": DEFAULT_TXT_ROOT,
    "excel_root": DEFAULT_EXCEL_ROOT,
    # Empty means "sync.db next to config.json" - resolved in database_file
    # below. Keeping the cache out of txt_root lets this app run alongside the
    # older single-workbook app without the two fighting over one sync.db.
    "database_file": "",
    "watch_extensions": [".txt"],
    "auto_start": False,
    "mapping_password": "2001",
    "dark_mode": False,
    "default_visibility": DEFAULT_VISIBILITY,
    # Breaking LT Category: the first N lines take the earlier time, every
    # line after them (including newly-added ones) takes the default.
    "default_category_time": DEFAULT_CATEGORY_TIME,
    "first_category_time": DEFAULT_FIRST_CATEGORY_TIME,
    "first_category_count": DEFAULT_FIRST_CATEGORY_COUNT,
    "feeds": copy.deepcopy(DEFAULT_FEEDS),
}

logger = logging.getLogger("taaza_news_excel_sync")


class Config:
    def __init__(self, path, base_dir=None):
        self.path = path
        self.base_dir = base_dir or os.path.dirname(os.path.abspath(path))
        self.data = copy.deepcopy(DEFAULT_CONFIG)
        self.load_error = None
        self.load()

    def load(self):
        """Merge config.json over the defaults.

        Read as utf-8-sig: Notepad and PowerShell both happily save UTF-8 with
        a BOM, and a plain utf-8 read chokes on it. Silently falling back to
        the defaults there would be dangerous - the app would quietly start
        writing to the DEFAULT Excel folder instead of the configured one - so
        an unreadable config is logged loudly and recorded in load_error.
        """
        self.load_error = None
        if not os.path.exists(self.path):
            return self.data
        try:
            with open(self.path, "r", encoding="utf-8-sig") as f:
                loaded = json.load(f)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            self.load_error = f"{self.path} could not be read ({exc}); using default settings."
            logger.error("%s", self.load_error)
            return self.data
        if not isinstance(loaded, dict):
            self.load_error = f"{self.path} is not a JSON object; using default settings."
            logger.error("%s", self.load_error)
            return self.data
        self.data.update(loaded)
        return self.data

    def save(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    @property
    def txt_root(self):
        return self.data["txt_root"]

    @txt_root.setter
    def txt_root(self, value):
        self.data["txt_root"] = value

    @property
    def excel_root(self):
        return self.data["excel_root"]

    @excel_root.setter
    def excel_root(self, value):
        self.data["excel_root"] = value

    @property
    def database_file(self):
        configured = self.data.get("database_file")
        if configured:
            return configured
        return os.path.join(self.base_dir, "sync.db")

    @database_file.setter
    def database_file(self, value):
        self.data["database_file"] = value

    # -- feeds ----------------------------------------------------------------

    @property
    def feeds(self):
        """The configured Feed objects, in display order."""
        return load_feeds(self.data.get("feeds"))

    def save_feeds(self, feeds):
        self.data["feeds"] = [feed.to_dict() for feed in feeds]

    def txt_path(self, feed):
        return os.path.join(self.txt_root, feed.txt_file)

    def excel_path(self, feed):
        return os.path.join(self.excel_root, feed.excel_file)

    @property
    def default_visibility(self):
        try:
            return int(self.data.get("default_visibility", DEFAULT_VISIBILITY))
        except (TypeError, ValueError):
            return DEFAULT_VISIBILITY

    @property
    def default_category_time(self):
        return self.data.get("default_category_time", DEFAULT_CATEGORY_TIME)

    @property
    def first_category_time(self):
        """Category time for the first `first_category_count` news lines."""
        return self.data.get("first_category_time", DEFAULT_FIRST_CATEGORY_TIME)

    @property
    def first_category_count(self):
        """How many leading news lines use first_category_time. 0 disables it."""
        try:
            return max(0, int(self.data.get("first_category_count", DEFAULT_FIRST_CATEGORY_COUNT)))
        except (TypeError, ValueError):
            return DEFAULT_FIRST_CATEGORY_COUNT
