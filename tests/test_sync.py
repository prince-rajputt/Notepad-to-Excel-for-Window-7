import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openpyxl import load_workbook

from app.config import Config
from app.database import Database
from app.sync_engine import SyncEngine


class TestSyncEngine(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="sync_test_")
        self.txt_root = os.path.join(self.tmp_dir, "notepad")
        os.makedirs(self.txt_root)

        self.config = Config(os.path.join(self.tmp_dir, "config.json"))
        self.config.txt_root = self.txt_root
        self.config.excel_file = os.path.join(self.txt_root, "All_Content.xlsx")
        self.config.database_file = os.path.join(self.txt_root, "sync.db")

        self.db = Database(self.config.database_file)
        self.engine = SyncEngine(self.db, self.config)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write_txt(self, name, content):
        path = os.path.join(self.txt_root, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def _news_data_rows(self):
        wb = load_workbook(self.config.excel_file)
        ws = wb["News Data"]
        return [tuple(c.value for c in ws[r]) for r in range(2, ws.max_row + 1)]

    def test_initial_scan_maps_row_number_and_category(self):
        self._write_txt("row_02.txt", "राष्ट्रीय समाचार <BITMAP>a.psd</BITMAP>")
        self._write_txt("row_03.txt", "बंगाल की खबर <BITMAP>a.psd</BITMAP>")
        self._write_txt("row_05.txt", "बिहार की खबर <BITMAP>a.psd</BITMAP>")

        self.engine.run_initial_scan()

        r2 = self.db.get_by_row_number(2)
        r3 = self.db.get_by_row_number(3)
        r5 = self.db.get_by_row_number(5)
        self.assertEqual(r2.category, "खबर India")
        self.assertEqual(r3.category, "खबर बंगाल")
        self.assertEqual(r5.category, "खबर बिहार")
        self.assertTrue(os.path.exists(self.config.excel_file))

    def test_one_row_per_news_line_in_excel(self):
        self._write_txt(
            "row_02.txt",
            "आज देश में बड़ी खबर सामने आई है। <BITMAP>a.psd</BITMAP>\n"
            "English only line.\n"
            "सरकार ने नई घोषणा की है। <BITMAP>a.psd</BITMAP>\n"
            "भारत में लोगों ने प्रतिक्रिया दी है। <BITMAP>a.psd</BITMAP>\n",
        )
        self.engine.run_initial_scan()
        rows = self._news_data_rows()
        self.assertEqual(rows, [
            (0, "खबर India", None),
            (1, "खबर India", "आज देश में बड़ी खबर सामने आई है।"),
            (1, "खबर India", "English only line."),
            (1, "खबर India", "सरकार ने नई घोषणा की है।"),
            (1, "खबर India", "भारत में लोगों ने प्रतिक्रिया दी है।"),
        ])

    def test_bitmap_removed_from_stored_content(self):
        self._write_txt(
            "row_02.txt",
            "राष्ट्रीय मंदिर के पास इलाके में भीषण आग <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
            "A major fire occurred near the temple.\n"
            "7 श्रद्धालुओं की मौत <BITMAP>:\\newsair\\logo.psd</BITMAP>\n",
        )
        self.engine.run_initial_scan()
        rec = self.db.get_by_row_number(2)
        self.assertNotIn("BITMAP", rec.content)
        self.assertNotIn("newsair", rec.content)
        self.assertNotIn("logo.psd", rec.content)

    def test_new_file_added_with_correct_row_and_category(self):
        path = self._write_txt("row_08.txt", "मनोरंजन की खबर आई है।")
        self.engine.handle_created(path)
        rec = self.db.get_by_row_number(8)
        self.assertEqual(rec.category, "Entertainment")

    def test_modify_replaces_news_rows_no_duplicates(self):
        path = self._write_txt("row_02.txt", "पुरानी खबर।")
        self.engine.run_initial_scan()

        time.sleep(0.05)
        with open(path, "w", encoding="utf-8") as f:
            f.write("नई खबर एक।\nनई खबर दो।")
        self.engine.handle_modified(path)

        rows = self._news_data_rows()
        self.assertEqual(rows, [
            (0, "खबर India", None),
            (1, "खबर India", "नई खबर एक।"),
            (1, "खबर India", "नई खबर दो।"),
        ])

    def test_delete_removes_news_and_placeholder_entirely(self):
        path = self._write_txt("row_03.txt", "बंगाल की खबर।")
        self.engine.run_initial_scan()

        os.remove(path)
        self.engine.handle_deleted(path)

        self.assertIsNone(self.db.get_by_row_number(3))
        rows = self._news_data_rows()
        self.assertEqual(rows, [])

    def test_delete_one_category_keeps_others(self):
        p2 = self._write_txt("row_02.txt", "समाचार दो।")
        p3 = self._write_txt("row_03.txt", "समाचार तीन।")
        self.engine.run_initial_scan()

        os.remove(p3)
        self.engine.handle_deleted(p3)

        rows = self._news_data_rows()
        categories = {r[1] for r in rows}
        self.assertEqual(categories, {"खबर India"})

    def test_recreate_after_delete_reappears_fresh(self):
        path = self._write_txt("row_03.txt", "पुरानी सामग्री।")
        self.engine.run_initial_scan()

        os.remove(path)
        self.engine.handle_deleted(path)

        new_path = self._write_txt("row_03.txt", "नई सामग्री।")
        self.engine.handle_created(new_path)

        rec = self.db.get_by_row_number(3)
        self.assertEqual(rec.category, "खबर बंगाल")
        self.assertEqual(rec.content, "नई सामग्री।")
        rows = self._news_data_rows()
        self.assertIn((1, "खबर बंगाल", "नई सामग्री।"), rows)

    def test_reconciliation_detects_offline_changes(self):
        p2 = self._write_txt("row_02.txt", "सामग्री दो।")
        self.engine.run_initial_scan()

        os.remove(p2)
        self._write_txt("row_03.txt", "सामग्री तीन।")

        self.engine.run_reconciliation()

        self.assertIsNone(self.db.get_by_row_number(2))
        self.assertIsNotNone(self.db.get_by_row_number(3))

    def test_duplicate_event_protection(self):
        path = self._write_txt("row_02.txt", "सामग्री।")
        self.engine.run_initial_scan()

        self.engine.handle_modified(path)
        self.engine.handle_modified(path)
        self.engine.handle_modified(path)

        all_records = self.db.get_all()
        self.assertEqual(len(all_records), 1)

    def test_english_only_file_kept(self):
        self._write_txt("row_07.txt", "This is an English message.\nThis contains no Hindi.")
        self.engine.run_initial_scan()
        rows = self._news_data_rows()
        self.assertEqual(rows, [
            (0, "Commentary Box", None),
            (1, "Commentary Box", "This is an English message."),
            (1, "Commentary Box", "This contains no Hindi."),
        ])

    def test_mixed_hindi_english_line_kept_whole(self):
        self._write_txt("row_02.txt", "भारत ने India के साथ नई बातचीत शुरू की <BITMAP>a.psd</BITMAP>")
        self.engine.run_initial_scan()
        rows = self._news_data_rows()
        self.assertIn((1, "खबर India", "भारत ने India के साथ नई बातचीत शुरू की"), rows)

    def test_non_matching_filename_ignored(self):
        self._write_txt("National.txt", "आज देश में खबर आई है।")
        self._write_txt("row_02.txt", "सही फाइल।")
        self.engine.run_initial_scan()
        records = self.db.get_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].row_number, 2)

    def test_disabled_row_file_is_completely_ignored(self):
        # Rows 1, 4, 9, 10 have no entry in the default row_categories whitelist -
        # their files must never be tracked or appear in Excel, even with valid Hindi content.
        self._write_txt("row_01.txt", "आज की मुख्य खबर है।")
        self._write_txt("row_04.txt", "बड़ी ब्रेकिंग न्यूज़।")
        self._write_txt("row_02.txt", "सक्षम श्रेणी की खबर।")
        self.engine.run_initial_scan()

        self.assertIsNone(self.db.get_by_row_number(1))
        self.assertIsNone(self.db.get_by_row_number(4))
        self.assertIsNotNone(self.db.get_by_row_number(2))

        rows = self._news_data_rows()
        categories = {r[1] for r in rows}
        self.assertNotIn("Top News", categories)
        self.assertNotIn("Breaking News", categories)
        self.assertIn("खबर India", categories)

    def test_reconciliation_refreshes_category_even_when_file_untouched(self):
        # Regression: if row_02.txt's size/mtime never change, a later config
        # edit renaming its category must still be picked up by the next scan -
        # not masked by the "unchanged file" fast path.
        self._write_txt("row_02.txt", "समाचार।")
        self.engine.run_initial_scan()
        self.assertEqual(self.db.get_by_row_number(2).category, "खबर India")

        # Edit config directly (simulating a stale config.json that predates a
        # rename, or a hand-edit), WITHOUT touching row_02.txt at all.
        self.config.set_category(2, "National")  # old stale name, for example
        self.config.save()
        self.engine.run_reconciliation()
        self.assertEqual(self.db.get_by_row_number(2).category, "National")

        # And the reverse: renaming back to the new name must also flow through.
        self.config.set_category(2, "खबर India")
        self.config.save()
        self.engine.run_reconciliation()
        self.assertEqual(self.db.get_by_row_number(2).category, "खबर India")
        rows = self._news_data_rows()
        categories = {r[1] for r in rows}
        self.assertIn("खबर India", categories)
        self.assertNotIn("National", categories)

    def test_previously_tracked_row_purged_when_removed_from_mapping(self):
        self._write_txt("row_02.txt", "समाचार।")
        self.engine.run_initial_scan()
        self.assertIsNotNone(self.db.get_by_row_number(2))

        # Simulate the user removing row 2 from the Row/Category Mapping editor.
        del self.config.row_categories["2"]
        self.config.save()
        self.engine.run_reconciliation()

        self.assertIsNone(self.db.get_by_row_number(2))
        rows = self._news_data_rows()
        self.assertEqual(rows, [])

    def test_refresh_categories_updates_existing_records(self):
        self._write_txt("row_02.txt", "राष्ट्रीय समाचार।")
        self.engine.run_initial_scan()
        self.assertEqual(self.db.get_by_row_number(2).category, "खबर India")

        self.config.set_category(2, "India Renamed")
        self.config.save()
        self.engine.refresh_categories()

        self.assertEqual(self.db.get_by_row_number(2).category, "India Renamed")
        rows = self._news_data_rows()
        categories = {r[1] for r in rows}
        self.assertIn("India Renamed", categories)

    def test_no_rows_for_files_that_dont_exist(self):
        self._write_txt("row_02.txt", "समाचार।")
        self.engine.run_initial_scan()
        rows = self._news_data_rows()
        categories = {r[1] for r in rows}
        self.assertNotIn("Top News", categories)
        self.assertNotIn("Breaking News", categories)


if __name__ == "__main__":
    unittest.main()
