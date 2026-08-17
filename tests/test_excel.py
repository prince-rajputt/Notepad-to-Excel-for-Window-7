import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import load_workbook

from app.database import Database
from app.excel_manager import generate_excel, HEADERS


class TestExcelManager(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="excel_test_")
        self.db = Database(os.path.join(self.tmp_dir, "sync.db"))
        self.excel_path = os.path.join(self.tmp_dir, "All_Content.xlsx")

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_generate_excel_basic_structure(self):
        self.db.upsert_row(
            2, "National", "row_02.txt", r"C:\notepad\row_02.txt",
            "राष्ट्रीय मंदिर के पास इलाके में भीषण आग\nसरकार ने नई घोषणा की है।",
            "hash1", 100, 1.0,
        )
        records = self.db.get_all()
        generate_excel(records, self.excel_path)

        self.assertTrue(os.path.exists(self.excel_path))
        wb = load_workbook(self.excel_path)
        self.assertIn("Content", wb.sheetnames)
        self.assertIn("Summary", wb.sheetnames)

        ws = wb["Content"]
        header_row = [c.value for c in ws[1]]
        self.assertEqual(header_row, HEADERS)

        row2 = [c.value for c in ws[2]]
        self.assertEqual(row2[0], 2)  # Serial No. = row number
        self.assertEqual(row2[1], "National")  # Category
        self.assertEqual(row2[2], "row_02.txt")  # File Name
        self.assertEqual(
            row2[3],
            "राष्ट्रीय मंदिर के पास इलाके में भीषण आग\nसरकार ने नई घोषणा की है।",
        )
        self.assertEqual(row2[7], "Active")

    def test_hindi_message_wrap_text_enabled(self):
        self.db.upsert_row(
            3, "Bengal", "row_03.txt", r"C:\notepad\row_03.txt", "भारत ने मैच जीता।", "h", 1, 1.0
        )
        generate_excel(self.db.get_all(), self.excel_path)
        wb = load_workbook(self.excel_path)
        ws = wb["Content"]
        cell = ws.cell(row=2, column=4)
        self.assertTrue(cell.alignment.wrap_text)
        self.assertEqual(cell.alignment.vertical, "top")

    def test_freeze_panes_and_autofilter(self):
        self.db.upsert_row(2, "National", "row_02.txt", r"C:\notepad\row_02.txt", "", "h", 1, 1.0)
        generate_excel(self.db.get_all(), self.excel_path)
        wb = load_workbook(self.excel_path)
        ws = wb["Content"]
        self.assertEqual(ws.freeze_panes, "A2")
        self.assertIsNotNone(ws.auto_filter.ref)

    def test_one_row_per_txt_file_not_per_line(self):
        self.db.upsert_row(
            2, "National", "row_02.txt", r"C:\notepad\row_02.txt",
            "line1\nline2\nline3", "h", 1, 1.0,
        )
        generate_excel(self.db.get_all(), self.excel_path)
        wb = load_workbook(self.excel_path)
        ws = wb["Content"]
        # header + exactly one data row
        self.assertEqual(ws.max_row, 2)

    def test_deleted_record_included_with_status(self):
        self.db.upsert_row(3, "Bengal", "row_03.txt", r"C:\notepad\row_03.txt", "content", "h", 1, 1.0)
        self.db.mark_deleted(3)
        generate_excel(self.db.get_all(), self.excel_path)
        wb = load_workbook(self.excel_path)
        ws = wb["Content"]
        row2 = [c.value for c in ws[2]]
        self.assertEqual(row2[7], "Deleted")
        self.assertIsNotNone(row2[6])

    def test_rows_sorted_by_serial_not_alphabetical_category(self):
        self.db.upsert_row(11, "Unassigned", "row_11.txt", r"C:\notepad\row_11.txt", "", "h", 1, 1.0)
        self.db.upsert_row(2, "National", "row_02.txt", r"C:\notepad\row_02.txt", "", "h", 1, 1.0)
        self.db.upsert_row(1, "Top News", "row_01.txt", r"C:\notepad\row_01.txt", "", "h", 1, 1.0)
        generate_excel(self.db.get_all(), self.excel_path)
        wb = load_workbook(self.excel_path)
        ws = wb["Content"]
        serials = [ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)]
        self.assertEqual(serials, [1, 2, 11])

    def test_summary_sheet_counts(self):
        self.db.upsert_row(2, "National", "row_02.txt", r"C:\notepad\row_02.txt", "", "h", 1, 1.0)
        self.db.upsert_row(3, "Bengal", "row_03.txt", r"C:\notepad\row_03.txt", "", "h", 1, 1.0)
        self.db.mark_deleted(2)
        generate_excel(self.db.get_all(), self.excel_path)
        wb = load_workbook(self.excel_path)
        ws = wb["Summary"]
        values = {ws.cell(row=r, column=1).value: ws.cell(row=r, column=2).value for r in range(1, ws.max_row + 1)}
        self.assertEqual(values["Total Word Files"], 2)
        self.assertEqual(values["Active Files"], 1)
        self.assertEqual(values["Deleted Files"], 1)


if __name__ == "__main__":
    unittest.main()
