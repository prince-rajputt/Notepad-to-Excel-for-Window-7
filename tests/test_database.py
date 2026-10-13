"""SQLite cache keyed by feed key."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Database


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = Database(os.path.join(self.tmp, "sync.db"))

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _insert(self, key="top_news", label="Top News", txt="row_01.txt",
                content="लाइन एक\nलाइन दो", file_hash="h1", size=100, mtime=1.0):
        return self.db.upsert_feed(
            key, label, txt, f"C:\\notepad\\{txt}", content, file_hash, size, mtime
        )

    def test_insert_then_fetch(self):
        rec = self._insert()
        self.assertEqual(rec.feed_key, "top_news")
        self.assertEqual(rec.label, "Top News")
        self.assertEqual(rec.txt_file, "row_01.txt")
        self.assertEqual(self.db.get_by_feed_key("top_news").id, rec.id)

    def test_news_lines_split_from_content(self):
        rec = self._insert(content="एक\nदो\nतीन")
        self.assertEqual(rec.news_lines, ["एक", "दो", "तीन"])

    def test_empty_content_yields_no_lines(self):
        self.assertEqual(self._insert(content="").news_lines, [])

    def test_upsert_updates_in_place_keeping_id(self):
        first = self._insert()
        second = self._insert(content="बदली हुई लाइन", file_hash="h2", size=200, mtime=2.0)
        self.assertEqual(first.id, second.id)
        self.assertEqual(second.content, "बदली हुई लाइन")
        self.assertEqual(len(self.db.get_all()), 1)

    def test_feed_key_is_unique(self):
        self._insert()
        self._insert()
        self.assertEqual(len(self.db.get_all()), 1)

    def test_multiple_feeds_coexist(self):
        self._insert("top_news", "Top News", "row_01.txt")
        self._insert("upper_band", "Upper Band", "row_10.txt")
        self._insert("breaking_news", "Breaking News", "row_04.txt")
        self.assertEqual(len(self.db.get_all()), 3)
        self.assertEqual(
            self.db.get_all_feed_keys(), {"top_news", "upper_band", "breaking_news"}
        )

    def test_delete_is_a_hard_delete(self):
        self._insert()
        self.db.delete_feed("top_news")
        self.assertIsNone(self.db.get_by_feed_key("top_news"))
        self.assertEqual(self.db.get_all(), [])

    def test_delete_of_unknown_key_is_a_no_op(self):
        self._insert()
        self.db.delete_feed("not_a_feed")
        self.assertEqual(len(self.db.get_all()), 1)

    def test_update_label(self):
        self._insert()
        self.db.update_label("top_news", "Renamed")
        self.assertEqual(self.db.get_by_feed_key("top_news").label, "Renamed")

    def test_touch_last_synced_leaves_content_alone(self):
        rec = self._insert()
        self.db.touch_last_synced("top_news")
        self.assertEqual(self.db.get_by_feed_key("top_news").content, rec.content)

    def test_search_matches_label_txt_file_and_key(self):
        self._insert("top_news", "Top News", "row_01.txt")
        self._insert("upper_band", "Upper Band", "row_10.txt")
        self.assertEqual(len(self.db.search("Upper")), 1)
        self.assertEqual(len(self.db.search("row_01")), 1)
        self.assertEqual(len(self.db.search("upper_band")), 1)
        self.assertEqual(len(self.db.search("nothing")), 0)

    def test_stats_counts_feeds_and_news_items(self):
        self._insert("top_news", "Top News", "row_01.txt", content="एक\nदो")
        self._insert("upper_band", "Upper Band", "row_10.txt", content="तीन")
        stats = self.db.stats()
        self.assertEqual(stats["total_files"], 2)
        self.assertEqual(stats["news_items"], 3)

    def test_stats_on_empty_database(self):
        self.assertEqual(self.db.stats(), {"total_files": 0, "news_items": 0})

    def test_schema_survives_reopen(self):
        self._insert()
        self.db.close()
        reopened = Database(os.path.join(self.tmp, "sync.db"))
        try:
            self.assertEqual(reopened.get_by_feed_key("top_news").txt_file, "row_01.txt")
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
