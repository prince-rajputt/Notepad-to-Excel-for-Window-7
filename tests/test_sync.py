"""Sync engine: per-feed create/modify/delete, strict source-file filtering."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl

from app.config import Config
from app.database import Database
from app.sync_engine import SyncEngine

BITMAP = "  <BITMAP>v:\\newsair\\logo.psd</BITMAP> "


class SyncTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.txt_root = os.path.join(self.tmp, "notepad")
        self.excel_root = os.path.join(self.tmp, "excel")
        os.makedirs(self.txt_root)
        os.makedirs(self.excel_root)

        self.config = Config(os.path.join(self.tmp, "config.json"), base_dir=self.tmp)
        self.config.txt_root = self.txt_root
        self.config.excel_root = self.excel_root

        self.db = Database(self.config.database_file)
        self.engine = SyncEngine(self.db, self.config)
        self.events = []
        self.engine.on_event = self.events.append

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_txt(self, name, lines, with_bitmap=True):
        path = os.path.join(self.txt_root, name)
        suffix = BITMAP if with_bitmap else ""
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write("\n".join(line + suffix for line in lines) + "\n")
        return path

    def feed(self, key):
        return {f.key: f for f in self.config.feeds}[key]

    def sheet(self, filename, sheet_name=None):
        wb = openpyxl.load_workbook(os.path.join(self.excel_root, filename))
        return wb[sheet_name] if sheet_name else wb.active

    def data_rows(self, filename, sheet_name=None):
        return self.sheet(filename, sheet_name).max_row - 1


class TestInitialScan(SyncTestCase):
    def test_all_four_workbooks_written_even_with_no_source_files(self):
        self.engine.run_initial_scan()
        self.assertEqual(
            sorted(os.listdir(self.excel_root)),
            ["Breaking FF + Top.xlsx", "Breaking LT.xlsx", "TopNewsLT.xlsx", "Upper Band.xlsx"],
        )

    def test_source_files_are_read_into_their_own_workbooks(self):
        self.write_txt("row_01.txt", ["टॉप एक", "टॉप दो"])
        self.write_txt("row_10.txt", ["अपर एक"])
        self.engine.run_initial_scan()
        self.assertEqual(self.data_rows("TopNewsLT.xlsx"), 2)
        self.assertEqual(self.data_rows("Upper Band.xlsx"), 1)
        self.assertEqual(self.data_rows("Breaking LT.xlsx", "Breaking LT News"), 0)

    def test_bitmap_tags_are_stripped(self):
        self.write_txt("row_01.txt", ["खबर एक"])
        self.engine.run_initial_scan()
        self.assertEqual(self.sheet("TopNewsLT.xlsx")["B2"].value, "खबर एक")

    def test_english_only_lines_are_kept(self):
        """Current behaviour keeps every non-empty line, Hindi or not."""
        self.write_txt("row_01.txt", ["हिंदी लाइन", "English only line"])
        self.engine.run_initial_scan()
        self.assertEqual(self.data_rows("TopNewsLT.xlsx"), 2)

    def test_bitmap_only_line_is_dropped(self):
        path = os.path.join(self.txt_root, "row_01.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write("असली खबर" + BITMAP + "\n" + BITMAP.strip() + "\n")
        self.engine.run_initial_scan()
        self.assertEqual(self.data_rows("TopNewsLT.xlsx"), 1)


class TestFileFiltering(SyncTestCase):
    def test_unconfigured_row_files_are_ignored(self):
        for name in ("row_02.txt", "row_03.txt", "row_05.txt", "row_11.txt"):
            self.write_txt(name, ["इसे नहीं पढ़ा जाए"])
        self.engine.run_initial_scan()
        self.assertEqual(self.db.get_all(), [])
        for row_rows in (
            self.data_rows("TopNewsLT.xlsx"),
            self.data_rows("Upper Band.xlsx"),
            self.data_rows("Breaking FF + Top.xlsx"),
        ):
            self.assertEqual(row_rows, 0)

    def test_subfolders_are_never_scanned(self):
        os.makedirs(os.path.join(self.txt_root, "archive"))
        with open(os.path.join(self.txt_root, "archive", "row_01.txt"), "w", encoding="utf-8") as f:
            f.write("सबफोल्डर लाइन\n")
        self.engine.run_initial_scan()
        self.assertEqual(self.data_rows("TopNewsLT.xlsx"), 0)

    def test_other_workbooks_in_excel_folder_are_untouched(self):
        decoy = os.path.join(self.excel_root, "Ticker_Taaza TV.xlsx")
        openpyxl.Workbook().save(decoy)
        before = os.path.getmtime(decoy)
        self.write_txt("row_01.txt", ["खबर"])
        self.engine.run_initial_scan()
        self.assertTrue(os.path.exists(decoy))
        self.assertEqual(os.path.getmtime(decoy), before)

    def test_feed_for_path_accepts_only_configured_names_in_root(self):
        accept = self.engine.feed_for_path(os.path.join(self.txt_root, "row_04.txt"))
        self.assertIsNotNone(accept)
        self.assertEqual(accept.excel_file, "Breaking LT.xlsx")

        self.assertIsNone(self.engine.feed_for_path(os.path.join(self.txt_root, "row_02.txt")))
        self.assertIsNone(
            self.engine.feed_for_path(os.path.join(self.txt_root, "sub", "row_01.txt"))
        )
        self.assertIsNone(self.engine.feed_for_path(os.path.join(self.tmp, "row_01.txt")))

    def test_feed_for_path_is_case_insensitive(self):
        self.assertIsNotNone(self.engine.feed_for_path(os.path.join(self.txt_root, "ROW_09.TXT")))


class TestModifyDeleteRecreate(SyncTestCase):
    def test_modify_replaces_rows_without_duplicating(self):
        self.write_txt("row_01.txt", ["पहली"])
        self.engine.run_initial_scan()
        self.write_txt("row_01.txt", ["पहली", "दूसरी", "तीसरी"])
        self.engine.run_reconciliation()
        self.assertEqual(self.data_rows("TopNewsLT.xlsx"), 3)
        self.assertEqual(len(self.db.get_all()), 1)

    def test_delete_empties_only_that_feeds_workbook(self):
        self.write_txt("row_01.txt", ["टॉप"])
        self.write_txt("row_04.txt", ["ब्रेकिंग"])
        self.engine.run_initial_scan()

        os.remove(os.path.join(self.txt_root, "row_04.txt"))
        self.engine.run_reconciliation()

        self.assertEqual(self.data_rows("Breaking LT.xlsx", "Breaking LT News"), 0)
        self.assertEqual(self.data_rows("Breaking LT.xlsx", "Breaking LT Category"), 0)
        self.assertEqual(self.data_rows("TopNewsLT.xlsx"), 1)
        self.assertIsNone(self.db.get_by_feed_key("breaking_news"))

    def test_deleted_workbook_keeps_its_headers(self):
        self.write_txt("row_10.txt", ["अपर"])
        self.engine.run_initial_scan()
        os.remove(os.path.join(self.txt_root, "row_10.txt"))
        self.engine.run_reconciliation()
        ws = self.sheet("Upper Band.xlsx")
        self.assertEqual([ws["A1"].value, ws["B1"].value], ["Visibility", "News"])

    def test_recreated_file_repopulates(self):
        self.write_txt("row_09.txt", ["पुरानी"])
        self.engine.run_initial_scan()
        os.remove(os.path.join(self.txt_root, "row_09.txt"))
        self.engine.run_reconciliation()
        self.write_txt("row_09.txt", ["नई एक", "नई दो"])
        self.engine.run_reconciliation()
        self.assertEqual(self.data_rows("Breaking FF + Top.xlsx"), 2)

    def test_handle_changed_ignores_non_feed_paths(self):
        path = self.write_txt("row_02.txt", ["नहीं"])
        self.assertIsNone(self.engine.handle_changed(path))
        self.assertEqual(self.db.get_all(), [])

    def test_handle_deleted_ignores_non_feed_paths(self):
        self.write_txt("row_01.txt", ["खबर"])
        self.engine.run_initial_scan()
        self.engine.handle_deleted(os.path.join(self.txt_root, "row_02.txt"))
        self.assertIsNotNone(self.db.get_by_feed_key("top_news"))

    def test_unchanged_file_is_not_reparsed(self):
        self.write_txt("row_01.txt", ["खबर"])
        self.engine.run_initial_scan()
        before = self.db.get_by_feed_key("top_news")
        self.engine.run_reconciliation()
        after = self.db.get_by_feed_key("top_news")
        self.assertEqual(before.modified_at, after.modified_at)


class TestDefaults(SyncTestCase):
    def test_visibility_defaults_to_one_across_all_feeds(self):
        self.write_txt("row_01.txt", ["क"])
        self.write_txt("row_10.txt", ["ख"])
        self.write_txt("row_04.txt", ["ग"])
        self.write_txt("row_09.txt", ["घ"])
        self.engine.run_initial_scan()
        self.assertEqual(self.sheet("TopNewsLT.xlsx")["A2"].value, 1)
        self.assertEqual(self.sheet("Upper Band.xlsx")["A2"].value, 1)
        self.assertEqual(self.sheet("Breaking LT.xlsx", "Breaking LT News")["A2"].value, 1)
        self.assertEqual(self.sheet("Breaking FF + Top.xlsx")["A2"].value, 1)

    def test_breaking_lt_first_two_are_8pm_rest_9pm(self):
        self.write_txt("row_04.txt", ["एक", "दो", "तीन", "चार"])
        self.engine.run_initial_scan()
        ws = self.sheet("Breaking LT.xlsx", "Breaking LT News")
        self.assertEqual(
            [str(ws.cell(r, 2).value) for r in range(2, 6)],
            ["20:00:00", "20:00:00", "21:00:00", "21:00:00"],
        )

    def test_breaking_lt_category_sheet_lists_both_times(self):
        self.write_txt("row_04.txt", ["एक", "दो", "तीन"])
        self.engine.run_initial_scan()
        cat = self.sheet("Breaking LT.xlsx", "Breaking LT Category")
        self.assertEqual(cat.max_row, 3)
        self.assertEqual([str(cat["B2"].value), str(cat["B3"].value)],
                         ["20:00:00", "21:00:00"])

    def test_line_added_later_takes_the_default_time(self):
        self.write_txt("row_04.txt", ["एक", "दो"])
        self.engine.run_initial_scan()
        self.write_txt("row_04.txt", ["एक", "दो", "नई खबर"])
        self.engine.run_reconciliation()
        ws = self.sheet("Breaking LT.xlsx", "Breaking LT News")
        self.assertEqual(str(ws["B2"].value), "20:00:00")
        self.assertEqual(str(ws["B4"].value), "21:00:00")

    def test_configured_defaults_are_used(self):
        self.config.set("default_visibility", 0)
        self.config.set("default_category_time", "10:00:00 PM")
        self.config.set("first_category_count", 0)
        self.write_txt("row_04.txt", ["ब्रेकिंग"])
        self.engine.run_initial_scan()
        ws = self.sheet("Breaking LT.xlsx", "Breaking LT News")
        self.assertEqual(ws["A2"].value, 0)
        self.assertEqual(str(ws["B2"].value), "22:00:00")

    def test_split_is_configurable(self):
        self.config.set("first_category_time", "06:00:00 AM")
        self.config.set("first_category_count", 1)
        self.write_txt("row_04.txt", ["एक", "दो"])
        self.engine.run_initial_scan()
        ws = self.sheet("Breaking LT.xlsx", "Breaking LT News")
        self.assertEqual(str(ws["B2"].value), "06:00:00")
        self.assertEqual(str(ws["B3"].value), "21:00:00")


class TestStaleFeedCleanup(SyncTestCase):
    def test_records_for_removed_feeds_are_purged(self):
        self.write_txt("row_01.txt", ["खबर"])
        self.engine.run_initial_scan()
        self.assertIsNotNone(self.db.get_by_feed_key("top_news"))

        remaining = [f for f in self.config.feeds if f.key != "top_news"]
        self.config.save_feeds(remaining)

        self.engine.run_reconciliation()
        self.assertIsNone(self.db.get_by_feed_key("top_news"))


if __name__ == "__main__":
    unittest.main()
