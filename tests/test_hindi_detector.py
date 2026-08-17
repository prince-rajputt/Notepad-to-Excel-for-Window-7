import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.hindi_detector import contains_devanagari, filter_hindi_lines


class TestHindiDetector(unittest.TestCase):
    def test_pure_hindi(self):
        self.assertTrue(contains_devanagari("आज भारत में बारिश हुई।"))

    def test_pure_english(self):
        self.assertFalse(contains_devanagari("India won the match."))

    def test_mixed_hindi_english(self):
        self.assertTrue(contains_devanagari("भारत ने India को हराया।"))

    def test_hindi_with_english_word(self):
        self.assertTrue(contains_devanagari("आज India में बारिश हुई।"))

    def test_empty_string(self):
        self.assertFalse(contains_devanagari(""))

    def test_none(self):
        self.assertFalse(contains_devanagari(None))

    def test_whitespace_only(self):
        self.assertFalse(contains_devanagari("   \t  "))

    def test_breaking_news(self):
        self.assertFalse(contains_devanagari("Breaking News"))

    def test_mixed_line_kept_completely(self):
        line = "भारत ने India को हराया।"
        result = filter_hindi_lines([line])
        self.assertEqual(result, [line])
        self.assertIn("India", result[0])

    def test_filter_hindi_lines_mixed_list(self):
        lines = [
            "आज देश में नई घोषणा की गई है।",
            "A new announcement has been made in the country.",
            "सरकार ने नई योजना शुरू की है।",
            "",
            "   ",
            "The government has launched a new scheme.",
            "लोगों ने इस योजना का स्वागत किया।",
        ]
        expected = [
            "आज देश में नई घोषणा की गई है।",
            "सरकार ने नई योजना शुरू की है।",
            "लोगों ने इस योजना का स्वागत किया।",
        ]
        self.assertEqual(filter_hindi_lines(lines), expected)


if __name__ == "__main__":
    unittest.main()
