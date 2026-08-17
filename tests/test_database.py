import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Database
from app.models import STATUS_ACTIVE, STATUS_DELETED


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="db_test_")
        self.db_path = os.path.join(self.tmp_dir, "sync.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()

    def test_insert_and_get_by_row_number(self):
        rec = self.db.upsert_row(
            2, "National", "row_02.txt", r"C:\notepad\row_02.txt",
            "content", "hash1", 100, 123.0,
        )
        self.assertEqual(rec.row_number, 2)
        self.assertEqual(rec.serial_number, 2)
        self.assertEqual(rec.status, STATUS_ACTIVE)
        fetched = self.db.get_by_row_number(2)
        self.assertEqual(fetched.file_name, "row_02.txt")

    def test_upsert_updates_existing_row_keeps_row_number(self):
        rec = self.db.upsert_row(
            2, "National", "row_02.txt", r"C:\notepad\row_02.txt",
            "old content", "hash1", 100, 123.0,
        )
        updated = self.db.upsert_row(
            2, "National", "row_02.txt", r"C:\notepad\row_02.txt",
            "new content", "hash2", 120, 200.0,
        )
        self.assertEqual(updated.row_number, rec.row_number)
        self.assertEqual(updated.content, "new content")
        self.assertEqual(updated.created_at, rec.created_at)  # created_at preserved

    def test_mark_deleted_keeps_record(self):
        rec = self.db.upsert_row(
            3, "Bengal", "row_03.txt", r"C:\notepad\row_03.txt",
            "content", "hash1", 100, 123.0,
        )
        deleted = self.db.mark_deleted(3)
        self.assertEqual(deleted.status, STATUS_DELETED)
        self.assertIsNotNone(deleted.deleted_at)
        self.assertEqual(deleted.row_number, rec.row_number)

    def test_recreate_reactivates_same_row(self):
        self.db.upsert_row(3, "Bengal", "row_03.txt", r"C:\notepad\row_03.txt", "old", "h1", 1, 1.0)
        self.db.mark_deleted(3)
        recreated = self.db.upsert_row(3, "Bengal", "row_03.txt", r"C:\notepad\row_03.txt", "new", "h2", 2, 2.0)
        self.assertEqual(recreated.row_number, 3)
        self.assertEqual(recreated.status, STATUS_ACTIVE)
        self.assertIsNone(recreated.deleted_at)
        self.assertEqual(recreated.content, "new")

    def test_search_by_category_and_filename(self):
        self.db.upsert_row(2, "National", "row_02.txt", r"C:\notepad\row_02.txt", "", "h", 1, 1.0)
        self.db.upsert_row(3, "Bengal", "row_03.txt", r"C:\notepad\row_03.txt", "", "h", 1, 1.0)
        results = self.db.search("Bengal")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].category, "Bengal")
        results2 = self.db.search("row_02")
        self.assertEqual(len(results2), 1)

    def test_status_filter(self):
        self.db.upsert_row(2, "National", "row_02.txt", r"C:\notepad\row_02.txt", "", "h", 1, 1.0)
        self.db.upsert_row(3, "Bengal", "row_03.txt", r"C:\notepad\row_03.txt", "", "h", 1, 1.0)
        self.db.mark_deleted(2)
        active = self.db.get_all(status=STATUS_ACTIVE)
        deleted = self.db.get_all(status=STATUS_DELETED)
        self.assertEqual(len(active), 1)
        self.assertEqual(len(deleted), 1)

    def test_refresh_categories(self):
        self.db.upsert_row(2, "National", "row_02.txt", r"C:\notepad\row_02.txt", "", "h", 1, 1.0)
        self.db.upsert_row(3, "Bengal", "row_03.txt", r"C:\notepad\row_03.txt", "", "h", 1, 1.0)
        mapping = {2: "National Renamed", 3: "Bengal Renamed"}
        self.db.refresh_categories(lambda row_number: mapping.get(row_number, "Unassigned"))
        self.assertEqual(self.db.get_by_row_number(2).category, "National Renamed")
        self.assertEqual(self.db.get_by_row_number(3).category, "Bengal Renamed")

    def test_stats(self):
        self.db.upsert_row(2, "National", "row_02.txt", r"C:\notepad\row_02.txt", "", "h", 1, 1.0)
        self.db.upsert_row(3, "Bengal", "row_03.txt", r"C:\notepad\row_03.txt", "", "h", 1, 1.0)
        self.db.mark_deleted(2)
        stats = self.db.stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["active"], 1)
        self.assertEqual(stats["deleted"], 1)


if __name__ == "__main__":
    unittest.main()
