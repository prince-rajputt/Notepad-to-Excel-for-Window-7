"""Map row_XX.txt filenames to their permanent row number and category.

row_categories in config.json is a WHITELIST: only row numbers present as
keys are tracked at all. A row_XX.txt whose number has no entry is skipped
entirely (as if it didn't match the row_XX.txt pattern) - it never appears
in the database or in Excel, even if the file exists on disk.
"""
import re

ROW_FILENAME_PATTERN = re.compile(r"^row_(\d+)\.txt$", re.IGNORECASE)

# Only these rows are tracked by default. Add more via the GUI's
# Row/Category Mapping editor (or config.json) to enable additional rows.
DEFAULT_ROW_CATEGORIES = {
    "2": "खबर India",
    "3": "खबर बंगाल",
    "5": "खबर बिहार",
    "6": "खबर झारखंड",
    "7": "Commentary Box",
    "8": "Entertainment",
    "11": "Advertisement",
}

UNASSIGNED_CATEGORY = "Unassigned"


def parse_row_number(filename):
    """Return the integer row number for a row_XX.txt filename, or None if the
    filename doesn't match the row_XX.txt pattern (case-insensitive)."""
    match = ROW_FILENAME_PATTERN.match(filename)
    if not match:
        return None
    return int(match.group(1))


def is_row_enabled(row_number, config):
    """True only if row_number has an explicit entry in the configured
    row_categories whitelist."""
    row_categories = config.get("row_categories", DEFAULT_ROW_CATEGORIES)
    return str(row_number) in row_categories


def category_for_row(row_number, config):
    """Look up the configured category name for a row number, defaulting to
    'Unassigned' for any row number that has no explicit mapping yet.

    Only call this for a row_number that is_row_enabled() has already
    confirmed - process_file() must skip disabled rows before ever reaching
    the point of needing a category name.
    """
    row_categories = config.get("row_categories", DEFAULT_ROW_CATEGORIES)
    return row_categories.get(str(row_number), UNASSIGNED_CATEGORY)
