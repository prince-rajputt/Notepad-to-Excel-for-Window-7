import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import load_workbook

from app.database import Database
from app.excel_manager import generate_excel, NEWS_CATEGORY_HEADERS, NEWS_DATA_HEADERS
from app.row_mapping import DEFAULT_ROW_CATEGORIES


class TestExcelManager(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="excel_test_")
        self.db = Database(os.path.join(self.tmp_dir, "sync.db"))
        self.excel_path = os.path.join(self.tmp_dir, "All_Content.xlsx")

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_two_sheets_only(self):
        generate_excel(self.db.get_all(), self.excel_path, DEFAULT_ROW_CATEGORIES)
        wb = load_workbook(self.excel_path)
        self.assertEqual(wb.sheetnames, ["News Data", "News Category"])

    def test_news_data_headers(self):
        generate_excel(self.db.get_all(), self.excel_path, DEFAULT_ROW_CATEGORIES)
        wb = load_workbook(self.excel_path)
        ws = wb["News Data"]
        header_row = [c.value for c in ws[1]]
        self.assertEqual(header_row, NEWS_DATA_HEADERS)

    def test_one_row_per_news_line_with_placeholder(self):
        self.db.upsert_row(
            2, "खबर India", "row_02.txt", r"C:\notepad\row_02.txt",
            "आज देश में बड़ी खबर सामने आई है।\nसरकार ने नई घोषणा की है।\nभारत में लोगों ने प्रतिक्रिया दी है।",
            "h", 1, 1.0,
        )
        generate_excel(self.db.get_all(), self.excel_path, DEFAULT_ROW_CATEGORIES)
        wb = load_workbook(self.excel_path)
        ws = wb["News Data"]

        rows = [tuple(c.value for c in ws[r]) for r in range(2, ws.max_row + 1)]
        self.assertEqual(rows, [
            (0, "खबर India", None),
            (1, "खबर India", "आज देश में बड़ी खबर सामने आई है।"),
            (1, "खबर India", "सरकार ने नई घोषणा की है।"),
            (1, "खबर India", "भारत में लोगों ने प्रतिक्रिया दी है।"),
        ])

    def test_empty_content_only_placeholder_no_news_rows(self):
        self.db.upsert_row(9, "Full Screen Breaking", "row_09.txt", r"C:\notepad\row_09.txt", "", "h", 1, 1.0)
        generate_excel(self.db.get_all(), self.excel_path, DEFAULT_ROW_CATEGORIES)
        wb = load_workbook(self.excel_path)
        ws = wb["News Data"]
        rows = [tuple(c.value for c in ws[r]) for r in range(2, ws.max_row + 1)]
        self.assertEqual(rows, [(0, "Full Screen Breaking", None)])

    def test_all_placeholders_before_all_news_rows(self):
        self.db.upsert_row(2, "खबर India", "row_02.txt", r"C:\notepad\row_02.txt", "समाचार एक।", "h", 1, 1.0)
        self.db.upsert_row(3, "खबर बंगाल", "row_03.txt", r"C:\notepad\row_03.txt", "समाचार दो।", "h", 1, 1.0)
        generate_excel(self.db.get_all(), self.excel_path, DEFAULT_ROW_CATEGORIES)
        wb = load_workbook(self.excel_path)
        ws = wb["News Data"]
        rows = [tuple(c.value for c in ws[r]) for r in range(2, ws.max_row + 1)]
        self.assertEqual(rows, [
            (0, "खबर India", None),
            (0, "खबर बंगाल", None),
            (1, "खबर India", "समाचार एक।"),
            (1, "खबर बंगाल", "समाचार दो।"),
        ])

    def test_no_rows_for_categories_without_existing_files(self):
        # Only row 2 exists; rows for Top News (1), Breaking News (4), etc. must not appear.
        self.db.upsert_row(2, "खबर India", "row_02.txt", r"C:\notepad\row_02.txt", "समाचार।", "h", 1, 1.0)
        generate_excel(self.db.get_all(), self.excel_path, DEFAULT_ROW_CATEGORIES)
        wb = load_workbook(self.excel_path)
        ws = wb["News Data"]
        categories_present = {ws.cell(row=r, column=2).value for r in range(2, ws.max_row + 1)}
        self.assertEqual(categories_present, {"खबर India"})

    def test_header_yellow_and_bold(self):
        generate_excel(self.db.get_all(), self.excel_path, DEFAULT_ROW_CATEGORIES)
        wb = load_workbook(self.excel_path)
        ws = wb["News Data"]
        cell = ws.cell(row=1, column=1)
        self.assertTrue(cell.font.bold)
        self.assertEqual(cell.fill.start_color.rgb, "00FFFF00")

    def test_freeze_panes_and_autofilter(self):
        generate_excel(self.db.get_all(), self.excel_path, DEFAULT_ROW_CATEGORIES)
        wb = load_workbook(self.excel_path)
        ws = wb["News Data"]
        self.assertEqual(ws.freeze_panes, "A2")
        self.assertIsNotNone(ws.auto_filter.ref)

    def test_news_category_sheet_lists_full_configured_mapping(self):
        # Even with zero active files, News Category shows the full 11-row mapping.
        generate_excel(self.db.get_all(), self.excel_path, DEFAULT_ROW_CATEGORIES)
        wb = load_workbook(self.excel_path)
        ws = wb["News Category"]
        header_row = [c.value for c in ws[1]]
        self.assertEqual(header_row, NEWS_CATEGORY_HEADERS)
        rows = [tuple(c.value for c in ws[r]) for r in range(2, ws.max_row + 1)]
        self.assertEqual(rows, [
            (2, "खबर India"), (3, "खबर बंगाल"), (5, "खबर बिहार"), (6, "खबर झारखंड"),
            (7, "Commentary Box"), (8, "Entertainment"), (11, "Advertisement"),
        ])

    def test_rows_grouped_by_row_number_order_not_alphabetical(self):
        self.db.upsert_row(11, "Advertisement", "row_11.txt", r"C:\notepad\row_11.txt", "विज्ञापन।", "h", 1, 1.0)
        self.db.upsert_row(2, "खबर India", "row_02.txt", r"C:\notepad\row_02.txt", "समाचार।", "h", 1, 1.0)
        generate_excel(self.db.get_all(), self.excel_path, DEFAULT_ROW_CATEGORIES)
        wb = load_workbook(self.excel_path)
        ws = wb["News Data"]
        placeholder_categories = [ws.cell(row=r, column=2).value for r in (2, 3)]
        self.assertEqual(placeholder_categories, ["खबर India", "Advertisement"])


if __name__ == "__main__":
    unittest.main()
