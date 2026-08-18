import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Database


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="db_test_")
        self.db_path = os.path.join(self.tmp_dir, "sync.db")
        self.db = Database(self.db_path)

    def tearDown(self):
        self.db.close()

    def test_insert_and_get_by_row_number(self):
        rec = self.db.upsert_row(
            2, "खबर India", "row_02.txt", r"C:\notepad\row_02.txt",
            "content", "hash1", 100, 123.0,
        )
        self.assertEqual(rec.row_number, 2)
        fetched = self.db.get_by_row_number(2)
        self.assertEqual(fetched.file_name, "row_02.txt")

    def test_upsert_updates_existing_row_keeps_row_number(self):
        rec = self.db.upsert_row(
            2, "खबर India", "row_02.txt", r"C:\notepad\row_02.txt",
            "old content", "hash1", 100, 123.0,
        )
        updated = self.db.upsert_row(
            2, "खबर India", "row_02.txt", r"C:\notepad\row_02.txt",
            "new content", "hash2", 120, 200.0,
        )
        self.assertEqual(updated.row_number, rec.row_number)
        self.assertEqual(updated.content, "new content")
        self.assertEqual(updated.created_at, rec.created_at)  # created_at preserved

    def test_delete_row_removes_record_entirely(self):
        self.db.upsert_row(3, "खबर बंगाल", "row_03.txt", r"C:\notepad\row_03.txt", "content", "hash1", 100, 123.0)
        self.db.delete_row(3)
        self.assertIsNone(self.db.get_by_row_number(3))
        self.assertEqual(self.db.get_all(), [])

    def test_recreate_after_delete_is_a_fresh_insert(self):
        self.db.upsert_row(3, "खबर बंगाल", "row_03.txt", r"C:\notepad\row_03.txt", "old", "h1", 1, 1.0)
        self.db.delete_row(3)
        recreated = self.db.upsert_row(3, "खबर बंगाल", "row_03.txt", r"C:\notepad\row_03.txt", "new", "h2", 2, 2.0)
        self.assertEqual(recreated.row_number, 3)
        self.assertEqual(recreated.content, "new")

    def test_search_by_category_and_filename(self):
        self.db.upsert_row(2, "खबर India", "row_02.txt", r"C:\notepad\row_02.txt", "", "h", 1, 1.0)
        self.db.upsert_row(3, "खबर बंगाल", "row_03.txt", r"C:\notepad\row_03.txt", "", "h", 1, 1.0)
        results = self.db.search("बंगाल")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].category, "खबर बंगाल")
        results2 = self.db.search("row_02")
        self.assertEqual(len(results2), 1)

    def test_get_all_row_numbers(self):
        self.db.upsert_row(2, "खबर India", "row_02.txt", r"C:\notepad\row_02.txt", "", "h", 1, 1.0)
        self.db.upsert_row(5, "खबर बिहार", "row_05.txt", r"C:\notepad\row_05.txt", "", "h", 1, 1.0)
        self.assertEqual(self.db.get_all_row_numbers(), {2, 5})

    def test_refresh_categories(self):
        self.db.upsert_row(2, "खबर India", "row_02.txt", r"C:\notepad\row_02.txt", "", "h", 1, 1.0)
        self.db.upsert_row(3, "खबर बंगाल", "row_03.txt", r"C:\notepad\row_03.txt", "", "h", 1, 1.0)
        mapping = {2: "India Renamed", 3: "Bengal Renamed"}
        self.db.refresh_categories(lambda row_number: mapping.get(row_number, "Unassigned"))
        self.assertEqual(self.db.get_by_row_number(2).category, "India Renamed")
        self.assertEqual(self.db.get_by_row_number(3).category, "Bengal Renamed")

    def test_stats(self):
        self.db.upsert_row(2, "खबर India", "row_02.txt", r"C:\notepad\row_02.txt", "line1\nline2", "h", 1, 1.0)
        self.db.upsert_row(3, "खबर बंगाल", "row_03.txt", r"C:\notepad\row_03.txt", "line1\nline2\nline3", "h", 1, 1.0)
        stats = self.db.stats()
        self.assertEqual(stats["total_files"], 2)
        self.assertEqual(stats["news_items"], 5)
        self.assertEqual(stats["active_categories"], 2)

    def test_stats_empty_content_counts_zero_news_items(self):
        self.db.upsert_row(9, "Full Screen Breaking", "row_09.txt", r"C:\notepad\row_09.txt", "", "h", 1, 1.0)
        stats = self.db.stats()
        self.assertEqual(stats["total_files"], 1)
        self.assertEqual(stats["news_items"], 0)


if __name__ == "__main__":
    unittest.main()
