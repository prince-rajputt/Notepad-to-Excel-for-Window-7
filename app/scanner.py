"""Filesystem helpers for locating the configured feed source files.

Deliberately narrow: the app never enumerates a folder looking for work. It
only ever asks for the exact file names it was configured with, directly
inside the one root folder. Subfolders and every other .txt file present are
invisible to it.
"""
import logging
import os

logger = logging.getLogger("taaza_news_excel_sync")


def resolve_feed_paths(root_folder, feeds):
    """Return {feed_key: full_path} for the configured feeds' source files.

    Paths are returned whether or not the file exists - the caller decides
    what a missing source file means (it empties that feed's workbook).
    """
    return {feed.key: os.path.join(root_folder, feed.txt_file) for feed in feeds}


def existing_feed_paths(root_folder, feeds):
    """Return {feed_key: full_path} for only those source files present on disk."""
    if not os.path.isdir(root_folder):
        logger.warning("TXT root folder does not exist: %s", root_folder)
        return {}
    return {
        key: path
        for key, path in resolve_feed_paths(root_folder, feeds).items()
        if os.path.isfile(path)
    }


def get_file_stat(full_path):
    """Return (size, mtime) for a file, or (None, None) if it cannot be stat'd."""
    try:
        st = os.stat(full_path)
        return st.st_size, st.st_mtime
    except OSError:
        return None, None
