"""Feed definitions: one source .txt file -> one Excel workbook, one format.

This replaces the old "row_XX.txt -> category -> shared All_Content.xlsx"
model. There are now exactly four independent feeds, each with its own source
file, its own destination workbook, and its own column layout dictated by the
broadcast software that reads it.

Only the .txt files named here are ever read, and only the .xlsx files named
here are ever written - every other file in either folder is ignored.
"""
from dataclasses import dataclass, field
from datetime import time as dt_time

# -- workbook layouts ---------------------------------------------------------
# Each constant names one on-disk column layout. The writers live in
# excel_manager.py; see that module for the exact fonts/fills/widths.

FORMAT_STATUS_NEWS = "status_news"
"""A=Status, B=News. Nirmala UI 11, bold+yellow header, freeze + autofilter."""

FORMAT_VISIBILITY_NEWS = "visibility_news"
"""A=Visibility, B=News. Arial 10, yellow header. No freeze, no autofilter."""

FORMAT_BREAKING_LT = "breaking_lt"
"""Two sheets: A=Visibility, B=Category (time), C=News, plus a Category sheet."""


DEFAULT_VISIBILITY = 1

# Breaking LT's Category column carries a time the .txt file does not supply.
# The first few news lines take an earlier slot, everything after them falls
# back to the default - matching how the workbook is filled in by hand.
DEFAULT_CATEGORY_TIME = "09:00:00 PM"
DEFAULT_FIRST_CATEGORY_TIME = "08:00:00 PM"
DEFAULT_FIRST_CATEGORY_COUNT = 2

# Excel's own time format string for the Category column, matching the
# existing Breaking LT.xlsx byte-for-byte.
CATEGORY_NUMBER_FORMAT = "hh:mm:ss\\ AM/PM"


@dataclass(frozen=True)
class Feed:
    """One source .txt file synchronized into one destination .xlsx workbook."""

    key: str
    label: str
    txt_file: str
    excel_file: str
    excel_format: str
    sheet_name: str
    category_sheet_name: str = ""
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data):
        return cls(
            key=data["key"],
            label=data.get("label", data["key"]),
            txt_file=data["txt_file"],
            excel_file=data["excel_file"],
            excel_format=data.get("excel_format", FORMAT_VISIBILITY_NEWS),
            sheet_name=data.get("sheet_name", "Sheet1"),
            category_sheet_name=data.get("category_sheet_name", ""),
        )

    def to_dict(self):
        data = {
            "key": self.key,
            "label": self.label,
            "txt_file": self.txt_file,
            "excel_file": self.excel_file,
            "excel_format": self.excel_format,
            "sheet_name": self.sheet_name,
        }
        if self.category_sheet_name:
            data["category_sheet_name"] = self.category_sheet_name
        return data


DEFAULT_FEEDS = [
    {
        "key": "top_news",
        "label": "Top News",
        "txt_file": "row_01.txt",
        "excel_file": "TopNewsLT.xlsx",
        "excel_format": FORMAT_STATUS_NEWS,
        "sheet_name": "TopNews",
    },
    {
        "key": "upper_band",
        "label": "Upper Band",
        "txt_file": "row_10.txt",
        "excel_file": "Upper Band.xlsx",
        "excel_format": FORMAT_VISIBILITY_NEWS,
        "sheet_name": "Breaking News FF",
    },
    {
        "key": "breaking_news",
        "label": "Breaking News",
        "txt_file": "row_04.txt",
        "excel_file": "Breaking LT.xlsx",
        "excel_format": FORMAT_BREAKING_LT,
        "sheet_name": "Breaking LT News",
        "category_sheet_name": "Breaking LT Category",
    },
    {
        "key": "full_screen_breaking",
        "label": "Full Screen Breaking",
        "txt_file": "row_09.txt",
        "excel_file": "Breaking FF + Top.xlsx",
        "excel_format": FORMAT_VISIBILITY_NEWS,
        "sheet_name": "Breaking News FF",
    },
]


# Old default names the playout software has since stopped matching on. An
# existing config.json still carrying one of these exact values is upgraded on
# load instead of silently writing the wrong file/sheet. A name the user has
# customized under FEED MAPPING never matches, so it is left alone.
LEGACY_FEED_VALUES = {
    ("top_news", "sheet_name", "Top News LT"): "TopNews",
    ("top_news", "excel_file", "Top News LT.xlsx"): "TopNewsLT.xlsx",
}


def _upgrade_legacy_values(entry):
    upgraded = dict(entry)
    for (key, field_name, old_value), new_value in LEGACY_FEED_VALUES.items():
        if upgraded.get("key") == key and upgraded.get(field_name) == old_value:
            upgraded[field_name] = new_value
    return upgraded


def load_feeds(config_feeds):
    """Build the Feed list from config.json's "feeds" array, falling back to
    DEFAULT_FEEDS if it is missing or malformed."""
    if not config_feeds:
        config_feeds = DEFAULT_FEEDS
    feeds = []
    for entry in config_feeds:
        try:
            feeds.append(Feed.from_dict(_upgrade_legacy_values(entry)))
        except (KeyError, TypeError, ValueError):
            continue
    return feeds or [Feed.from_dict(e) for e in DEFAULT_FEEDS]


def feed_for_txt_filename(filename, feeds):
    """Return the Feed whose source file is `filename`, or None.

    Matching is exact (case-insensitive) on the file name only: a folder full
    of other row_XX.txt files must not be picked up, so there is deliberately
    no pattern matching here.
    """
    lowered = (filename or "").lower()
    for feed in feeds:
        if feed.txt_file.lower() == lowered:
            return feed
    return None


def is_feed_txt_file(filename, feeds):
    return feed_for_txt_filename(filename, feeds) is not None


def parse_category_time(value):
    """Parse a "09:00:00 PM"-style string into a datetime.time.

    Falls back to the 09:00:00 PM default for anything unparseable so a typo
    in config.json can never stop the workbook from being written.
    """
    if isinstance(value, dt_time):
        return value
    text = str(value or "").strip().upper()
    for fmt in ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            from datetime import datetime

            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    return dt_time(21, 0, 0)


def format_category_time(value):
    """Render a datetime.time back as "09:00:00 PM" for display/config."""
    if not isinstance(value, dt_time):
        value = parse_category_time(value)
    return value.strftime("%I:%M:%S %p")


def resolve_category_times(line_count, default_time, first_time=None, first_count=0):
    """Return one datetime.time per news line.

    The first `first_count` lines get `first_time`; every line after that -
    including every line added later - gets `default_time`.
    """
    default_value = parse_category_time(default_time)
    if not first_time or first_count <= 0:
        return [default_value] * line_count
    first_value = parse_category_time(first_time)
    return [
        first_value if index < first_count else default_value
        for index in range(line_count)
    ]


def distinct_in_order(values):
    """Unique values, keeping first-appearance order (for the Category sheet)."""
    seen = set()
    result = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
