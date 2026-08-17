"""Filesystem scanning helpers - list source files directly inside the root folder."""
import logging
import os

from app.utils import is_supported_file

logger = logging.getLogger("word_to_excel_sync")


def list_target_files(root_folder, extensions):
    """Return full paths of all real, supported files directly inside root_folder.

    Deliberately non-recursive: there must be no category subfolders, all
    source files live directly in the one monitored root folder.
    """
    if not os.path.isdir(root_folder):
        logger.warning("Root folder does not exist: %s", root_folder)
        return []

    paths = []
    try:
        entries = os.listdir(root_folder)
    except OSError as exc:
        logger.error("Failed to list folder %s: %s", root_folder, exc)
        return []

    for entry in entries:
        full_path = os.path.join(root_folder, entry)
        if not os.path.isfile(full_path):
            continue
        if is_supported_file(entry, extensions):
            paths.append(full_path)
    return paths


def get_file_stat(full_path):
    """Return (size, mtime) for a file, or (None, None) if it cannot be stat'd."""
    try:
        st = os.stat(full_path)
        return st.st_size, st.st_mtime
    except OSError:
        return None, None
