"""Generate and update the single All_Content.xlsx workbook from the database."""
import logging
import os
import tempfile
import time

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from app.models import STATUS_ACTIVE, STATUS_DELETED
from app.utils import now_str

logger = logging.getLogger("word_to_excel_sync")

HEADERS = [
    "Serial No.", "Category", "File Name", "Hindi Message", "Created At",
    "Modified At", "Deleted At", "Status", "Last Synced At",
]

COLUMN_WIDTHS = {
    "A": 12, "B": 25, "C": 18, "D": 80, "E": 22, "F": 22, "G": 22, "H": 15, "I": 22,
}


class ExcelLockedError(Exception):
    """Raised when All_Content.xlsx cannot be written because it is locked/open."""


def _build_workbook(records):
    wb = Workbook()
    ws = wb.active
    ws.title = "Content"

    header_font = Font(bold=True)
    header_align = Alignment(horizontal="center", vertical="center")
    for col_idx, header in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.alignment = header_align

    wrap_top = Alignment(wrap_text=True, vertical="top")
    top_align = Alignment(vertical="top")

    for row_idx, rec in enumerate(records, start=2):
        ws.cell(row=row_idx, column=1, value=rec.serial_number).alignment = top_align
        ws.cell(row=row_idx, column=2, value=rec.category).alignment = top_align
        ws.cell(row=row_idx, column=3, value=rec.file_name).alignment = top_align
        hindi_cell = ws.cell(row=row_idx, column=4, value=rec.content or "")
        hindi_cell.alignment = wrap_top
        ws.cell(row=row_idx, column=5, value=rec.created_at).alignment = top_align
        ws.cell(row=row_idx, column=6, value=rec.modified_at).alignment = top_align
        ws.cell(row=row_idx, column=7, value=rec.deleted_at or "").alignment = top_align
        ws.cell(row=row_idx, column=8, value=rec.status).alignment = top_align
        ws.cell(row=row_idx, column=9, value=rec.last_synced_at or "").alignment = top_align

    for col_letter, width in COLUMN_WIDTHS.items():
        ws.column_dimensions[col_letter].width = width

    last_row = max(len(records) + 1, 1)
    last_col = get_column_letter(len(HEADERS))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{last_col}{last_row}"

    _build_summary_sheet(wb, records)
    return wb


def _build_summary_sheet(wb, records):
    ws = wb.create_sheet("Summary")
    total = len(records)
    active = sum(1 for r in records if r.status == STATUS_ACTIVE)
    deleted = sum(1 for r in records if r.status == STATUS_DELETED)

    rows = [
        ("Total Word Files", total),
        ("Active Files", active),
        ("Deleted Files", deleted),
        ("Last Sync", now_str()),
    ]
    for row_idx, (label, value) in enumerate(rows, start=1):
        ws.cell(row=row_idx, column=1, value=label).font = Font(bold=True)
        ws.cell(row=row_idx, column=2, value=value)
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 22


def generate_excel(records, excel_path, attempts=3, base_delay=1.0):
    """Write records to excel_path using safe temp-file replacement, retrying on lock errors.

    Raises ExcelLockedError if the file is still locked after all attempts.
    Never leaves a corrupt/partial file at excel_path.
    """
    os.makedirs(os.path.dirname(os.path.abspath(excel_path)), exist_ok=True)
    wb = _build_workbook(records)

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
