"""Map row_XX.txt filenames to their permanent row number and category."""
import re

ROW_FILENAME_PATTERN = re.compile(r"^row_(\d+)\.txt$", re.IGNORECASE)

DEFAULT_ROW_CATEGORIES = {
    "1": "Top News",
    "2": "National",
    "3": "Bengal",
    "4": "Breaking News",
    "5": "Khabar Bihar",
    "6": "Khabar Jharkhand",
    "7": "Commentary Box",
    "8": "Entertainment Ticket",
    "9": "Full Screen Breaking",
    "10": "Upper Band",
    "11": "Unassigned",
}

UNASSIGNED_CATEGORY = "Unassigned"


def parse_row_number(filename):
    """Return the integer row number for a row_XX.txt filename, or None if the
    filename doesn't match the row_XX.txt pattern (case-insensitive)."""
    match = ROW_FILENAME_PATTERN.match(filename)
    if not match:
        return None
    return int(match.group(1))


def category_for_row(row_number, config):
    """Look up the configured category name for a row number, defaulting to
    'Unassigned' for any row number that has no explicit mapping yet."""
    row_categories = config.get("row_categories", DEFAULT_ROW_CATEGORIES)
    return row_categories.get(str(row_number), UNASSIGNED_CATEGORY)
