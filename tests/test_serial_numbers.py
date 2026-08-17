import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Database


class TestSerialNumbers(unittest.TestCase):
    """The row number parsed from row_XX.txt IS the permanent Excel serial
    number: it never dynamically renumbers, and recreating row_XX.txt reuses
    the same serial number rather than getting a new one (spec sections 3, 24)."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="serial_test_")
        self.db = Database(os.path.join(self.tmp_dir, "sync.db"))

    def tearDown(self):
        self.db.close()

    def test_row_number_is_serial_number(self):
        categories = {
            1: "Top News", 2: "National", 3: "Bengal", 4: "Breaking News",
            5: "Khabar Bihar", 6: "Khabar Jharkhand", 7: "Commentary Box",
            8: "Entertainment Ticket", 9: "Full Screen Breaking",
            10: "Upper Band", 11: "Unassigned",
        }
        for row_number, category in categories.items():
            filename = f"row_{row_number:02d}.txt"
            rec = self.db.upsert_row(
                row_number, category, filename, rf"C:\notepad\{filename}", "", "h", 1, 1.0
            )
            self.assertEqual(rec.serial_number, row_number)

    def test_serial_stable_after_modification(self):
        rec = self.db.upsert_row(2, "National", "row_02.txt", r"C:\notepad\row_02.txt", "old", "h1", 1, 1.0)
        self.assertEqual(rec.serial_number, 2)
        updated = self.db.upsert_row(2, "National", "row_02.txt", r"C:\notepad\row_02.txt", "new", "h2", 2, 2.0)
        self.assertEqual(updated.serial_number, 2)

    def test_serial_not_renumbered_after_delete(self):
        self.db.upsert_row(2, "National", "row_02.txt", r"C:\notepad\row_02.txt", "", "h", 1, 1.0)
        self.db.upsert_row(3, "Bengal", "row_03.txt", r"C:\notepad\row_03.txt", "", "h", 1, 1.0)
        self.db.mark_deleted(2)
        remaining = self.db.get_by_row_number(3)
        self.assertEqual(remaining.serial_number, 3)  # unaffected by row 2's deletion

    def test_recreated_file_keeps_same_serial(self):
        r1 = self.db.upsert_row(3, "Bengal", "row_03.txt", r"C:\notepad\row_03.txt", "old", "h1", 1, 1.0)
        self.db.mark_deleted(3)
        r2 = self.db.upsert_row(3, "Bengal", "row_03.txt", r"C:\notepad\row_03.txt", "new", "h2", 1, 1.0)
        self.assertEqual(r1.serial_number, r2.serial_number)
        self.assertEqual(r2.serial_number, 3)


if __name__ == "__main__":
    unittest.main()
