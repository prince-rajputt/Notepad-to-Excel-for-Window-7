"""Feed definitions, source-file matching, and category-time parsing."""
import os
import sys
import unittest
from datetime import time as dt_time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.feeds import (
    DEFAULT_FEEDS,
    FORMAT_BREAKING_LT,
    FORMAT_STATUS_NEWS,
    FORMAT_VISIBILITY_NEWS,
    Feed,
    distinct_in_order,
    feed_for_txt_filename,
    format_category_time,
    is_feed_txt_file,
    load_feeds,
    parse_category_time,
    resolve_category_times,
)


class TestDefaultFeeds(unittest.TestCase):
    def setUp(self):
        self.feeds = load_feeds(None)

    def test_exactly_four_feeds(self):
        self.assertEqual(len(self.feeds), 4)

    def test_expected_txt_to_excel_mapping(self):
        mapping = {f.txt_file: f.excel_file for f in self.feeds}
        self.assertEqual(
            mapping,
            {
                "row_01.txt": "TopNewsLT.xlsx",
                "row_10.txt": "Upper Band.xlsx",
                "row_04.txt": "Breaking LT.xlsx",
                "row_09.txt": "Breaking FF + Top.xlsx",
            },
        )

    def test_formats_and_sheet_names(self):
        by_key = {f.key: f for f in self.feeds}
        self.assertEqual(by_key["top_news"].excel_format, FORMAT_STATUS_NEWS)
        self.assertEqual(by_key["top_news"].sheet_name, "TopNews")

        self.assertEqual(by_key["upper_band"].excel_format, FORMAT_VISIBILITY_NEWS)
        self.assertEqual(by_key["upper_band"].sheet_name, "Breaking News FF")

        self.assertEqual(by_key["breaking_news"].excel_format, FORMAT_BREAKING_LT)
        self.assertEqual(by_key["breaking_news"].sheet_name, "Breaking LT News")
        self.assertEqual(by_key["breaking_news"].category_sheet_name, "Breaking LT Category")

        self.assertEqual(by_key["full_screen_breaking"].excel_format, FORMAT_VISIBILITY_NEWS)
        self.assertEqual(by_key["full_screen_breaking"].sheet_name, "Breaking News FF")

    def test_keys_are_unique(self):
        keys = [f.key for f in self.feeds]
        self.assertEqual(len(keys), len(set(keys)))

    def test_round_trip_through_dict(self):
        for feed in self.feeds:
            self.assertEqual(Feed.from_dict(feed.to_dict()), feed)


class TestFeedMatching(unittest.TestCase):
    def setUp(self):
        self.feeds = load_feeds(None)

    def test_matches_configured_source_file(self):
        feed = feed_for_txt_filename("row_04.txt", self.feeds)
        self.assertIsNotNone(feed)
        self.assertEqual(feed.excel_file, "Breaking LT.xlsx")

    def test_matching_is_case_insensitive(self):
        self.assertIsNotNone(feed_for_txt_filename("ROW_09.TXT", self.feeds))

    def test_unconfigured_row_files_are_not_matched(self):
        # The folder contains row_01..row_11; only four of them are feeds.
        for name in ("row_02.txt", "row_03.txt", "row_05.txt", "row_06.txt",
                     "row_07.txt", "row_08.txt", "row_11.txt"):
            self.assertIsNone(feed_for_txt_filename(name, self.feeds), name)

    def test_near_miss_names_are_not_matched(self):
        for name in ("row_1.txt", "row_01.txt.bak", "row_01.csv", "copy of row_01.txt", ""):
            self.assertIsNone(feed_for_txt_filename(name, self.feeds), name)

    def test_is_feed_txt_file(self):
        self.assertTrue(is_feed_txt_file("row_10.txt", self.feeds))
        self.assertFalse(is_feed_txt_file("row_11.txt", self.feeds))


class TestLoadFeeds(unittest.TestCase):
    def test_empty_config_falls_back_to_defaults(self):
        self.assertEqual(len(load_feeds(None)), len(DEFAULT_FEEDS))
        self.assertEqual(len(load_feeds([])), len(DEFAULT_FEEDS))

    def test_malformed_entries_are_skipped(self):
        feeds = load_feeds([
            {"key": "good", "txt_file": "a.txt", "excel_file": "a.xlsx", "sheet_name": "S"},
            {"missing": "required keys"},
        ])
        self.assertEqual([f.key for f in feeds], ["good"])

    def test_all_malformed_falls_back_to_defaults(self):
        self.assertEqual(len(load_feeds([{"nope": 1}])), len(DEFAULT_FEEDS))

    def test_old_top_news_names_are_upgraded(self):
        # A config.json saved before the playout software renamed the file and sheet.
        feeds = load_feeds([
            {"key": "top_news", "txt_file": "row_01.txt", "excel_file": "Top News LT.xlsx",
             "excel_format": FORMAT_STATUS_NEWS, "sheet_name": "Top News LT"},
        ])
        self.assertEqual(feeds[0].sheet_name, "TopNews")
        self.assertEqual(feeds[0].excel_file, "TopNewsLT.xlsx")

    def test_upgrade_only_applies_to_the_top_news_feed(self):
        feeds = load_feeds([
            {"key": "other", "txt_file": "a.txt", "excel_file": "a.xlsx", "sheet_name": "Top News LT"},
        ])
        self.assertEqual(feeds[0].sheet_name, "Top News LT")


class TestCategoryTime(unittest.TestCase):
    def test_parses_12_hour_with_seconds(self):
        self.assertEqual(parse_category_time("09:00:00 PM"), dt_time(21, 0, 0))
        self.assertEqual(parse_category_time("08:00:00 PM"), dt_time(20, 0, 0))
        self.assertEqual(parse_category_time("07:30:00 AM"), dt_time(7, 30, 0))

    def test_parses_other_common_forms(self):
        self.assertEqual(parse_category_time("9:00 PM"), dt_time(21, 0, 0))
        self.assertEqual(parse_category_time("21:00:00"), dt_time(21, 0, 0))
        self.assertEqual(parse_category_time("21:00"), dt_time(21, 0, 0))

    def test_lowercase_meridiem_accepted(self):
        self.assertEqual(parse_category_time("09:00:00 pm"), dt_time(21, 0, 0))

    def test_unparseable_falls_back_to_9pm_default(self):
        for bad in ("", None, "not a time", "25:99:99"):
            self.assertEqual(parse_category_time(bad), dt_time(21, 0, 0), bad)

    def test_passthrough_of_time_object(self):
        self.assertEqual(parse_category_time(dt_time(6, 15)), dt_time(6, 15))

    def test_format_round_trip(self):
        self.assertEqual(format_category_time("09:00:00 PM"), "09:00:00 PM")
        self.assertEqual(format_category_time(dt_time(20, 0)), "08:00:00 PM")


class TestResolveCategoryTimes(unittest.TestCase):
    def test_first_two_then_default(self):
        self.assertEqual(
            resolve_category_times(5, "09:00:00 PM", "08:00:00 PM", 2),
            [dt_time(20, 0), dt_time(20, 0), dt_time(21, 0), dt_time(21, 0), dt_time(21, 0)],
        )

    def test_count_zero_means_all_default(self):
        self.assertEqual(
            resolve_category_times(3, "09:00:00 PM", "08:00:00 PM", 0),
            [dt_time(21, 0)] * 3,
        )

    def test_no_first_time_means_all_default(self):
        self.assertEqual(
            resolve_category_times(2, "09:00:00 PM", None, 2), [dt_time(21, 0)] * 2
        )

    def test_count_larger_than_line_count(self):
        self.assertEqual(
            resolve_category_times(2, "09:00:00 PM", "08:00:00 PM", 10),
            [dt_time(20, 0), dt_time(20, 0)],
        )

    def test_no_lines_yields_empty_list(self):
        self.assertEqual(resolve_category_times(0, "09:00:00 PM", "08:00:00 PM", 2), [])

    def test_length_always_matches_line_count(self):
        for n in range(0, 8):
            self.assertEqual(len(resolve_category_times(n, "09:00:00 PM", "08:00:00 PM", 2)), n)


class TestDistinctInOrder(unittest.TestCase):
    def test_keeps_first_appearance_order(self):
        self.assertEqual(distinct_in_order([3, 1, 3, 2, 1]), [3, 1, 2])

    def test_empty(self):
        self.assertEqual(distinct_in_order([]), [])

    def test_all_identical_collapses_to_one(self):
        self.assertEqual(distinct_in_order(["a", "a", "a"]), ["a"])


if __name__ == "__main__":
    unittest.main()
