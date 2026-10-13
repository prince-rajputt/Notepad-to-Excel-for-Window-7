"""Generate each feed's own workbook from its extracted news lines.

Every workbook is a LIVE MIRROR of one .txt file: it is fully regenerated on
every sync, not incrementally patched, so deleted lines disappear and nothing
stale lingers.

The three layouts below were reverse-engineered from the workbooks the
broadcast software already reads, and reproduce their fonts, fills, column
widths and number formats exactly. Do not "tidy" them - the playout system
matches on these headers and sheet names.
"""
import logging
import os
import tempfile
import time

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.feeds import (
    CATEGORY_NUMBER_FORMAT,
    FORMAT_BREAKING_LT,
    FORMAT_STATUS_NEWS,
    FORMAT_VISIBILITY_NEWS,
    distinct_in_order,
    resolve_category_times,
)

logger = logging.getLogger("taaza_news_excel_sync")

HEADER_FILL = PatternFill(start_color="FFFFFF00", end_color="FFFFFF00", fill_type="solid")

# TopNewsLT.xlsx
STATUS_NEWS_FONT = "Nirmala UI"
STATUS_NEWS_SIZE = 11
STATUS_NEWS_HEADERS = ["Status", "News"]
STATUS_NEWS_WIDTHS = {"A": 13.0, "B": 100.0}

# Upper Band.xlsx / Breaking FF + Top.xlsx
VISIBILITY_NEWS_FONT = "Arial"
VISIBILITY_NEWS_SIZE = 10
VISIBILITY_NEWS_HEADERS = ["Visibility", "News"]
VISIBILITY_NEWS_WIDTHS = {"B": 68.7109375}

# Breaking LT.xlsx
BREAKING_LT_HEADERS = ["Visibility", "Category", "News"]
BREAKING_LT_WIDTHS = {"B": 20.42578125, "C": 57.0}
BREAKING_LT_CATEGORY_HEADERS = ["Visibility", "Category"]
BREAKING_LT_CATEGORY_WIDTHS = {"B": 23.5703125}


class ExcelLockedError(Exception):
    """Raised when a workbook cannot be written because it is locked/open."""


class UnknownFeedFormatError(Exception):
    """Raised when a feed names an excel_format with no writer."""


def _apply_widths(ws, widths):
    for col_letter, width in widths.items():
        ws.column_dimensions[col_letter].width = width


def _write_header(ws, headers, font, bold=False, centered=False):
    header_font = Font(name=font.name, sz=font.sz, bold=bold)
    align = Alignment(horizontal="center", vertical="center") if centered else None
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = HEADER_FILL
        if align is not None:
            cell.alignment = align


def _build_status_news(wb, feed, lines, defaults):
    """TopNewsLT.xlsx: A=Status, B=News, bold centered header, freeze+filter."""
    ws = wb.active
    ws.title = feed.sheet_name
    body_font = Font(name=STATUS_NEWS_FONT, sz=STATUS_NEWS_SIZE)
    _write_header(ws, STATUS_NEWS_HEADERS, body_font, bold=True, centered=True)

    top_align = Alignment(vertical="top")
    row_idx = 2
    for line in lines:
        status_cell = ws.cell(row=row_idx, column=1, value=defaults["visibility"])
        status_cell.font = body_font
        status_cell.alignment = top_align
        news_cell = ws.cell(row=row_idx, column=2, value=line)
        news_cell.font = body_font
        news_cell.alignment = top_align
        row_idx += 1

    _apply_widths(ws, STATUS_NEWS_WIDTHS)
    last_row = max(row_idx - 1, 1)
    last_col = get_column_letter(len(STATUS_NEWS_HEADERS))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{last_col}{last_row}"
    return ws


def _build_visibility_news(wb, feed, lines, defaults):
    """Upper Band.xlsx / Breaking FF + Top.xlsx: A=Visibility, B=News."""
    ws = wb.active
    ws.title = feed.sheet_name
    body_font = Font(name=VISIBILITY_NEWS_FONT, sz=VISIBILITY_NEWS_SIZE)
    _write_header(ws, VISIBILITY_NEWS_HEADERS, body_font)

    row_idx = 2
    for line in lines:
        ws.cell(row=row_idx, column=1, value=defaults["visibility"]).font = body_font
        ws.cell(row=row_idx, column=2, value=line).font = body_font
        row_idx += 1

    _apply_widths(ws, VISIBILITY_NEWS_WIDTHS)
    return ws


def _build_breaking_lt(wb, feed, lines, defaults):
    """Breaking LT.xlsx: a News sheet (Visibility/Category/News) plus a
    Category sheet listing the distinct category times in use.

    The first few lines take the earlier slot time and everything after them
    the default, so a newly-added line always lands on the default.
    """
    category_times = resolve_category_times(
        len(lines),
        defaults["category_time"],
        defaults.get("first_category_time"),
        defaults.get("first_category_count", 0),
    )

    ws = wb.active
    ws.title = feed.sheet_name
    body_font = Font(name=VISIBILITY_NEWS_FONT, sz=VISIBILITY_NEWS_SIZE)
    _write_header(ws, BREAKING_LT_HEADERS, body_font)

    for row_idx, (line, category_time) in enumerate(zip(lines, category_times), start=2):
        ws.cell(row=row_idx, column=1, value=defaults["visibility"]).font = body_font
        cat_cell = ws.cell(row=row_idx, column=2, value=category_time)
        cat_cell.font = body_font
        cat_cell.number_format = CATEGORY_NUMBER_FORMAT
        ws.cell(row=row_idx, column=3, value=line).font = body_font
    _apply_widths(ws, BREAKING_LT_WIDTHS)

    # The Category sheet lists each distinct time used by the News sheet once,
    # in the order it first appears - derived from the data, never hard-coded.
    cat_ws = wb.create_sheet(feed.category_sheet_name or "Category")
    _write_header(cat_ws, BREAKING_LT_CATEGORY_HEADERS, body_font)
    for cat_row_idx, value in enumerate(distinct_in_order(category_times), start=2):
        cat_ws.cell(row=cat_row_idx, column=1, value=defaults["visibility"]).font = body_font
        cell = cat_ws.cell(row=cat_row_idx, column=2, value=value)
        cell.font = body_font
        cell.number_format = CATEGORY_NUMBER_FORMAT
    _apply_widths(cat_ws, BREAKING_LT_CATEGORY_WIDTHS)
    return ws


_BUILDERS = {
    FORMAT_STATUS_NEWS: _build_status_news,
    FORMAT_VISIBILITY_NEWS: _build_visibility_news,
    FORMAT_BREAKING_LT: _build_breaking_lt,
}


def build_workbook(feed, lines, visibility, category_time,
                   first_category_time=None, first_category_count=0):
    """Build (but do not save) the workbook for one feed."""
    builder = _BUILDERS.get(feed.excel_format)
    if builder is None:
        raise UnknownFeedFormatError(
            f"Feed '{feed.key}' uses unknown excel_format '{feed.excel_format}'"
        )
    defaults = {
        "visibility": visibility,
        "category_time": category_time,
        "first_category_time": first_category_time,
        "first_category_count": first_category_count,
    }
    wb = Workbook()
    builder(wb, feed, lines, defaults)
    return wb


def generate_feed_excel(feed, lines, excel_path, visibility, category_time,
                        first_category_time=None, first_category_count=0,
                        attempts=3, base_delay=1.0):
    """Write one feed's workbook using safe temp-file replacement, retrying on
    lock errors.

    Raises ExcelLockedError if the file is still locked after all attempts.
    Never leaves a corrupt/partial file at excel_path.
    """
    target_dir = os.path.dirname(os.path.abspath(excel_path))
    os.makedirs(target_dir, exist_ok=True)
    wb = build_workbook(
        feed, lines, visibility, category_time, first_category_time, first_category_count
    )

    fd, tmp_path = tempfile.mkstemp(suffix=".xlsx", prefix=".~tmp_", dir=target_dir)
    os.close(fd)
    try:
        wb.save(tmp_path)

        delay = base_delay
        last_exc = None
        for attempt in range(1, attempts + 1):
            try:
                os.replace(tmp_path, excel_path)
                logger.info("Excel synchronized: %s", excel_path)
                return
            except PermissionError as exc:
                last_exc = exc
                logger.warning("Excel locked (attempt %s/%s): %s", attempt, attempts, excel_path)
                if attempt < attempts:
                    time.sleep(delay)
                    delay *= 2
        raise ExcelLockedError(
            f"Could not write {excel_path}: file appears to be open/locked"
        ) from last_exc
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
