"""Config loading, including the BOM / malformed-file safety net.

A config.json the app cannot parse must NOT silently fall back to the default
folders without saying so - that would mean writing to the wrong Excel folder.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import DEFAULT_EXCEL_ROOT, DEFAULT_TXT_ROOT, Config


class ConfigTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "config.json")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, text, encoding="utf-8"):
        with open(self.path, "w", encoding=encoding) as f:
            f.write(text)

    def write_json(self, data, encoding="utf-8"):
        self.write(json.dumps(data), encoding=encoding)


class TestDefaults(ConfigTestCase):
    def test_missing_file_uses_defaults_without_error(self):
        config = Config(self.path, base_dir=self.tmp)
        self.assertIsNone(config.load_error)
        self.assertEqual(config.txt_root, DEFAULT_TXT_ROOT)
        self.assertEqual(config.excel_root, DEFAULT_EXCEL_ROOT)

    def test_four_default_feeds(self):
        self.assertEqual(len(Config(self.path, base_dir=self.tmp).feeds), 4)

    def test_database_defaults_next_to_config(self):
        config = Config(self.path, base_dir=self.tmp)
        self.assertEqual(config.database_file, os.path.join(self.tmp, "sync.db"))

    def test_explicit_database_path_wins(self):
        self.write_json({"database_file": r"D:\elsewhere\sync.db"})
        self.assertEqual(Config(self.path, base_dir=self.tmp).database_file, r"D:\elsewhere\sync.db")

    def test_default_visibility_and_category(self):
        config = Config(self.path, base_dir=self.tmp)
        self.assertEqual(config.default_visibility, 1)
        self.assertEqual(config.default_category_time, "09:00:00 PM")


class TestLoading(ConfigTestCase):
    def test_configured_paths_are_honoured(self):
        self.write_json({"txt_root": r"D:\news", "excel_root": r"D:\out"})
        config = Config(self.path, base_dir=self.tmp)
        self.assertIsNone(config.load_error)
        self.assertEqual(config.txt_root, r"D:\news")
        self.assertEqual(config.excel_root, r"D:\out")

    def test_utf8_bom_file_still_loads(self):
        """PowerShell's Set-Content -Encoding UTF8 and Notepad both add a BOM."""
        self.write_json({"txt_root": r"D:\news"}, encoding="utf-8-sig")
        config = Config(self.path, base_dir=self.tmp)
        self.assertIsNone(config.load_error)
        self.assertEqual(config.txt_root, r"D:\news")

    def test_partial_config_keeps_other_defaults(self):
        self.write_json({"txt_root": r"D:\news"})
        config = Config(self.path, base_dir=self.tmp)
        self.assertEqual(config.excel_root, DEFAULT_EXCEL_ROOT)
        self.assertEqual(len(config.feeds), 4)

    def test_hindi_paths_survive_round_trip(self):
        config = Config(self.path, base_dir=self.tmp)
        config.txt_root = r"D:\खबर\notepad"
        config.save()
        self.assertEqual(Config(self.path, base_dir=self.tmp).txt_root, r"D:\खबर\notepad")

    def test_saved_config_reloads_without_error(self):
        config = Config(self.path, base_dir=self.tmp)
        config.save()
        self.assertIsNone(Config(self.path, base_dir=self.tmp).load_error)


class TestUnreadableConfigIsReported(ConfigTestCase):
    def test_malformed_json_sets_load_error(self):
        self.write("{ this is not json")
        config = Config(self.path, base_dir=self.tmp)
        self.assertIsNotNone(config.load_error)
        self.assertEqual(config.txt_root, DEFAULT_TXT_ROOT)

    def test_json_that_is_not_an_object_sets_load_error(self):
        self.write("[1, 2, 3]")
        config = Config(self.path, base_dir=self.tmp)
        self.assertIsNotNone(config.load_error)
        self.assertEqual(config.txt_root, DEFAULT_TXT_ROOT)

    def test_empty_file_sets_load_error(self):
        self.write("")
        self.assertIsNotNone(Config(self.path, base_dir=self.tmp).load_error)

    def test_undecodable_bytes_set_load_error(self):
        with open(self.path, "wb") as f:
            f.write(b"\xff\xfe\x00\x00garbage")
        self.assertIsNotNone(Config(self.path, base_dir=self.tmp).load_error)


class TestFeedPaths(ConfigTestCase):
    def test_txt_and_excel_paths_join_the_roots(self):
        self.write_json({"txt_root": r"D:\news", "excel_root": r"D:\out"})
        config = Config(self.path, base_dir=self.tmp)
        feed = {f.key: f for f in config.feeds}["breaking_news"]
        self.assertEqual(config.txt_path(feed), os.path.join(r"D:\news", "row_04.txt"))
        self.assertEqual(config.excel_path(feed), os.path.join(r"D:\out", "Breaking LT.xlsx"))

    def test_save_feeds_round_trips(self):
        config = Config(self.path, base_dir=self.tmp)
        feeds = config.feeds
        config.save_feeds(feeds)
        config.save()
        self.assertEqual([f.to_dict() for f in Config(self.path, base_dir=self.tmp).feeds],
                         [f.to_dict() for f in feeds])


if __name__ == "__main__":
    unittest.main()
