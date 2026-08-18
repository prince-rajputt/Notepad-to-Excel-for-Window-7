"""Generate and update the single All_Content.xlsx workbook from the database.

The workbook is a LIVE MIRROR of the currently-existing row_XX.txt files:
it is fully regenerated from the database on every sync, not incrementally
patched, so deleted files' news disappears and nothing stale lingers.
"""
import logging
import os
import tempfile
import time

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

logger = logging.getLogger("word_to_excel_sync")

NEWS_DATA_HEADERS = ["Visibility", "Category", "News Data"]
NEWS_DATA_COLUMN_WIDTHS = {"A": 13, "B": 28, "C": 90}

NEWS_CATEGORY_HEADERS = ["Row No.", "Category"]
NEWS_CATEGORY_COLUMN_WIDTHS = {"A": 12, "B": 30}

HEADER_FILL = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
UNICODE_FONT_NAME = "Nirmala UI"
WRAP_LENGTH_THRESHOLD = 100


class ExcelLockedError(Exception):
    """Raised when All_Content.xlsx cannot be written because it is locked/open."""


def _style_header_row(ws, headers):
    header_font = Font(bold=True, name=UNICODE_FONT_NAME)
    header_align = Alignment(horizontal="center", vertical="center")
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = HEADER_FILL
        cell.alignment = header_align


def _build_news_data_sheet(wb, records):
    ws = wb.active
    ws.title = "News Data"
    _style_header_row(ws, NEWS_DATA_HEADERS)

    body_font = Font(name=UNICODE_FONT_NAME)
    top_align = Alignment(vertical="top")

    row_idx = 2
    # Pass 1: one placeholder row (Visibility=0) per currently-active category,
    # in row-number order - all placeholders together, before any news rows.
    for rec in records:
        ws.cell(row=row_idx, column=1, value=0).font = body_font
        ws.cell(row=row_idx, column=1).alignment = top_align
        ws.cell(row=row_idx, column=2, value=rec.category).font = body_font
        ws.cell(row=row_idx, column=2).alignment = top_align
        ws.cell(row=row_idx, column=3, value="").font = body_font
        ws.cell(row=row_idx, column=3).alignment = top_align
        row_idx += 1

    # Pass 2: one row per Hindi news line, grouped by category in row-number order.
    for rec in records:
        for line in rec.news_lines:
            ws.cell(row=row_idx, column=1, value=1).font = body_font
            ws.cell(row=row_idx, column=1).alignment = top_align
            ws.cell(row=row_idx, column=2, value=rec.category).font = body_font
            ws.cell(row=row_idx, column=2).alignment = top_align
            news_cell = ws.cell(row=row_idx, column=3, value=line)
            news_cell.font = body_font
            wrap = len(line) > WRAP_LENGTH_THRESHOLD
            news_cell.alignment = Alignment(vertical="top", wrap_text=wrap)
            row_idx += 1

    for col_letter, width in NEWS_DATA_COLUMN_WIDTHS.items():
        ws.column_dimensions[col_letter].width = width

    last_row = max(row_idx - 1, 1)
    last_col = get_column_letter(len(NEWS_DATA_HEADERS))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{last_col}{last_row}"
    return ws


def _build_news_category_sheet(wb, row_categories):
    ws = wb.create_sheet("News Category")
    _style_header_row(ws, NEWS_CATEGORY_HEADERS)

    body_font = Font(name=UNICODE_FONT_NAME)
    for row_idx, row_number in enumerate(sorted((int(k) for k in row_categories.keys())), start=2):
        ws.cell(row=row_idx, column=1, value=row_number).font = body_font
        ws.cell(row=row_idx, column=2, value=row_categories[str(row_number)]).font = body_font

    for col_letter, width in NEWS_CATEGORY_COLUMN_WIDTHS.items():
        ws.column_dimensions[col_letter].width = width
    ws.freeze_panes = "A2"
    return ws


def _build_workbook(records, row_categories):
    wb = Workbook()
    _build_news_data_sheet(wb, records)
    _build_news_category_sheet(wb, row_categories)
    return wb


def generate_excel(records, excel_path, row_categories, attempts=3, base_delay=1.0):
    """Write records to excel_path using safe temp-file replacement, retrying on lock errors.

    Raises ExcelLockedError if the file is still locked after all attempts.
    Never leaves a corrupt/partial file at excel_path.
    """
    os.makedirs(os.path.dirname(os.path.abspath(excel_path)), exist_ok=True)
    wb = _build_workbook(records, row_categories)

    fd, tmp_path = tempfile.mkstemp(
        suffix=".xlsx", prefix=".~tmp_", dir=os.path.dirname(os.path.abspath(excel_path))
    )
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
                logger.warning(
                    "Excel locked (attempt %s/%s): %s", attempt, attempts, excel_path
                )
                if attempt < attempts:
                    time.sleep(delay)
                    delay *= 2
        raise ExcelLockedError(f"Could not write {excel_path}: file appears to be open/locked") from last_exc
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
