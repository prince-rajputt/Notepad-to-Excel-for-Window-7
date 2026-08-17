import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import Config
from app.database import Database
from app.models import STATUS_ACTIVE, STATUS_DELETED
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

    def test_initial_scan_maps_row_number_and_category(self):
        self._write_txt("row_01.txt", "आज की मुख्य खबर <BITMAP>a.psd</BITMAP>")
        self._write_txt("row_02.txt", "राष्ट्रीय समाचार <BITMAP>a.psd</BITMAP>")
        self._write_txt("row_03.txt", "बंगाल की खबर <BITMAP>a.psd</BITMAP>")

        self.engine.run_initial_scan()

        r1 = self.db.get_by_row_number(1)
        r2 = self.db.get_by_row_number(2)
        r3 = self.db.get_by_row_number(3)
        self.assertEqual(r1.category, "Top News")
        self.assertEqual(r2.category, "National")
        self.assertEqual(r3.category, "Bengal")
        self.assertEqual(r1.serial_number, 1)
        self.assertEqual(r2.serial_number, 2)
        self.assertEqual(r3.serial_number, 3)
        self.assertTrue(os.path.exists(self.config.excel_file))

    def test_unmapped_row_defaults_unassigned(self):
        self._write_txt("row_11.txt", "अनियत श्रेणी की खबर")
        self.engine.run_initial_scan()
        rec = self.db.get_by_row_number(11)
        self.assertEqual(rec.category, "Unassigned")

    def test_bitmap_removed_from_stored_content(self):
        self._write_txt(
            "row_02.txt",
            "राष्ट्रीय मंदिर के पास इलाके में भीषण आग <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
            "A major fire occurred near the temple.\n"
            "7 श्रद्धालुओं की मौत <BITMAP>:\\newsair\\logo.psd</BITMAP>\n",
        )
        self.engine.run_initial_scan()
        rec = self.db.get_by_row_number(2)
        self.assertEqual(
            rec.content,
            "राष्ट्रीय मंदिर के पास इलाके में भीषण आग\n7 श्रद्धालुओं की मौत",
        )
        self.assertNotIn("BITMAP", rec.content)
        self.assertNotIn("newsair", rec.content)
        self.assertNotIn("logo.psd", rec.content)

    def test_new_file_added_with_correct_row_and_category(self):
        path = self._write_txt("row_08.txt", "मनोरंजन की खबर आई है।")
        self.engine.handle_created(path)
        rec = self.db.get_by_row_number(8)
        self.assertEqual(rec.category, "Entertainment Ticket")
        self.assertEqual(rec.status, STATUS_ACTIVE)

    def test_modify_updates_same_row_number(self):
        path = self._write_txt("row_02.txt", "पुरानी खबर।")
        self.engine.run_initial_scan()
        before = self.db.get_by_row_number(2)

        time.sleep(0.05)
        with open(path, "w", encoding="utf-8") as f:
            f.write("नई खबर।")

        self.engine.handle_modified(path)
        after = self.db.get_by_row_number(2)

        self.assertEqual(after.row_number, before.row_number)
        self.assertEqual(after.content, "नई खबर।")
        self.assertEqual(after.created_at, before.created_at)

    def test_delete_marks_deleted_not_removed(self):
        path = self._write_txt("row_03.txt", "बंगाल की खबर।")
        self.engine.run_initial_scan()

        os.remove(path)
        self.engine.handle_deleted(path)

        rec = self.db.get_by_row_number(3)
        self.assertEqual(rec.status, STATUS_DELETED)
        self.assertIsNotNone(rec.deleted_at)
        self.assertEqual(rec.serial_number, 3)
        self.assertEqual(rec.category, "Bengal")  # historical content preserved

    def test_recreate_reuses_same_serial_and_category(self):
        path = self._write_txt("row_03.txt", "पुरानी सामग्री।")
        self.engine.run_initial_scan()

        os.remove(path)
        self.engine.handle_deleted(path)

        new_path = self._write_txt("row_03.txt", "नई सामग्री।")
        self.engine.handle_created(new_path)

        rec = self.db.get_by_row_number(3)
        self.assertEqual(rec.status, STATUS_ACTIVE)
        self.assertEqual(rec.serial_number, 3)
        self.assertEqual(rec.category, "Bengal")
        self.assertEqual(rec.content, "नई सामग्री।")
        self.assertIsNone(rec.deleted_at)
        # still exactly one record for row 3, not a new one
        all_row_3 = [r for r in self.db.get_all() if r.row_number == 3]
        self.assertEqual(len(all_row_3), 1)

    def test_reconciliation_detects_offline_changes(self):
        p1 = self._write_txt("row_01.txt", "सामग्री एक।")
        p2 = self._write_txt("row_02.txt", "सामग्री दो।")
        self.engine.run_initial_scan()

        os.remove(p2)
        p3 = self._write_txt("row_03.txt", "सामग्री तीन।")

        self.engine.run_reconciliation()

        self.assertEqual(self.db.get_by_row_number(2).status, STATUS_DELETED)
        self.assertIsNotNone(self.db.get_by_row_number(3))
        self.assertEqual(self.db.get_by_row_number(3).status, STATUS_ACTIVE)

    def test_duplicate_event_protection(self):
        path = self._write_txt("row_01.txt", "सामग्री।")
        self.engine.run_initial_scan()
        rec1 = self.db.get_by_row_number(1)

        self.engine.handle_modified(path)
        self.engine.handle_modified(path)
        self.engine.handle_modified(path)

        all_records = self.db.get_all()
        self.assertEqual(len(all_records), 1)
        self.assertEqual(all_records[0].row_number, rec1.row_number)

    def test_english_only_file_keeps_active_empty_message(self):
        path = self._write_txt("row_09.txt", "This is an English message.\nThis contains no Hindi.")
        self.engine.run_initial_scan()
        rec = self.db.get_by_row_number(9)
        self.assertEqual(rec.content, "")
        self.assertEqual(rec.status, STATUS_ACTIVE)

    def test_mixed_hindi_english_line_kept_whole(self):
        path = self._write_txt("row_02.txt", "भारत ने India के साथ नई बातचीत शुरू की <BITMAP>a.psd</BITMAP>")
        self.engine.run_initial_scan()
        rec = self.db.get_by_row_number(2)
        self.assertEqual(rec.content, "भारत ने India के साथ नई बातचीत शुरू की")

    def test_non_matching_filename_ignored(self):
        self._write_txt("National.txt", "आज देश में खबर आई है।")
        self._write_txt("row_01.txt", "सही फाइल।")
        self.engine.run_initial_scan()
        records = self.db.get_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].row_number, 1)

    def test_refresh_categories_updates_existing_records(self):
        self._write_txt("row_02.txt", "राष्ट्रीय समाचार।")
        self.engine.run_initial_scan()
        self.assertEqual(self.db.get_by_row_number(2).category, "National")

        self.config.set_category(2, "National Renamed")
        self.config.save()
        self.engine.refresh_categories()

        self.assertEqual(self.db.get_by_row_number(2).category, "National Renamed")

    def test_excel_row_order_matches_serial_not_alphabetical(self):
        self._write_txt("row_11.txt", "अनियत खबर।")
        self._write_txt("row_02.txt", "राष्ट्रीय खबर।")
        self._write_txt("row_01.txt", "मुख्य खबर।")
        self.engine.run_initial_scan()

        from openpyxl import load_workbook
        wb = load_workbook(self.config.excel_file)
        ws = wb["Content"]
        serials = [ws.cell(row=r, column=1).value for r in range(2, ws.max_row + 1)]
        self.assertEqual(serials, [1, 2, 11])


if __name__ == "__main__":
    unittest.main()
