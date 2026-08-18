import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.config import Config
from app.row_mapping import DEFAULT_ROW_CATEGORIES, category_for_row, is_row_enabled, parse_row_number


class TestParseRowNumber(unittest.TestCase):
    def test_standard_names(self):
        self.assertEqual(parse_row_number("row_01.txt"), 1)
        self.assertEqual(parse_row_number("row_02.txt"), 2)
        self.assertEqual(parse_row_number("row_11.txt"), 11)

    def test_case_insensitive_extension(self):
        self.assertEqual(parse_row_number("row_03.TXT"), 3)
        self.assertEqual(parse_row_number("ROW_03.txt"), 3)

    def test_multi_digit_row(self):
        self.assertEqual(parse_row_number("row_123.txt"), 123)

    def test_no_leading_zero_still_matches(self):
        self.assertEqual(parse_row_number("row_5.txt"), 5)

    def test_non_matching_filenames_return_none(self):
        self.assertIsNone(parse_row_number("National.txt"))
        self.assertIsNone(parse_row_number("row.txt"))
        self.assertIsNone(parse_row_number("row_ab.txt"))
        self.assertIsNone(parse_row_number("row_01.rtf"))
        self.assertIsNone(parse_row_number("row_01.docx"))
        self.assertIsNone(parse_row_number("~$row_01.txt"))
        self.assertIsNone(parse_row_number("row_01_backup.txt"))


class TestCategoryForRow(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="row_mapping_test_")
        self.config = Config(os.path.join(self.tmp_dir, "config.json"))

    def test_default_mapping_matches_spec(self):
        expected = {
            2: "खबर India", 3: "खबर बंगाल", 5: "खबर बिहार", 6: "खबर झारखंड",
            7: "Commentary Box", 8: "Entertainment", 11: "Advertisement",
        }
        for row_number, category in expected.items():
            self.assertEqual(category_for_row(row_number, self.config), category)

    def test_unmapped_row_defaults_to_unassigned(self):
        self.assertEqual(category_for_row(999, self.config), "Unassigned")

    def test_user_can_override_mapping(self):
        self.config.set_category(11, "Custom Category")
        self.config.save()
        self.assertEqual(category_for_row(11, self.config), "Custom Category")

    def test_default_row_categories_immutable_from_config_mutation(self):
        self.config.set_category(2, "Changed")
        self.assertEqual(DEFAULT_ROW_CATEGORIES["2"], "खबर India")


class TestIsRowEnabled(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="row_enabled_test_")
        self.config = Config(os.path.join(self.tmp_dir, "config.json"))

    def test_default_enabled_rows_only_the_seven_configured(self):
        for row_number in (2, 3, 5, 6, 7, 8, 11):
            self.assertTrue(is_row_enabled(row_number, self.config))

    def test_rows_not_in_mapping_are_disabled_by_default(self):
        for row_number in (1, 4, 9, 10):
            self.assertFalse(is_row_enabled(row_number, self.config))

    def test_adding_a_row_enables_it(self):
        self.assertFalse(is_row_enabled(1, self.config))
        self.config.set_category(1, "Top News")
        self.config.save()
        self.assertTrue(is_row_enabled(1, self.config))


if __name__ == "__main__":
    unittest.main()
