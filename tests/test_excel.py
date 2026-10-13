"""Workbook generation: one file per feed, each in its own exact layout."""
import os
import shutil
import sys
import tempfile
import unittest
from datetime import time as dt_time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl

from app.excel_manager import (
    ExcelLockedError,
    UnknownFeedFormatError,
    build_workbook,
    generate_feed_excel,
)
from app.feeds import Feed, load_feeds

HINDI_LINES = [
    "कोलकाता के जोड़ाबगान में पुराना मकान गिरा",
    "हादसे में एक की मौत, कई घायल, राहत कार्य जारी",
    "भारत ने India को हराया",
]


def feed(key):
    return {f.key: f for f in load_feeds(None)}[key]


class TestTopNewsLayout(unittest.TestCase):
    """TopNewsLT.xlsx: A=Status, B=News, Nirmala UI 11, bold yellow header."""

    @classmethod
    def setUpClass(cls):
        cls.ws = build_workbook(feed("top_news"), HINDI_LINES, 1, "09:00:00 PM").active

    def test_sheet_name(self):
        self.assertEqual(self.ws.title, "TopNews")

    def test_headers(self):
        self.assertEqual(self.ws["A1"].value, "Status")
        self.assertEqual(self.ws["B1"].value, "News")

    def test_header_is_bold_yellow_and_centered(self):
        cell = self.ws["A1"]
        self.assertTrue(cell.font.b)
        self.assertEqual(cell.fill.start_color.rgb, "FFFFFF00")
        self.assertEqual(cell.alignment.horizontal, "center")

    def test_unicode_font_for_hindi(self):
        self.assertEqual(self.ws["B2"].font.name, "Nirmala UI")
        self.assertEqual(self.ws["B2"].font.sz, 11)

    def test_one_row_per_news_line(self):
        self.assertEqual(self.ws.max_row, len(HINDI_LINES) + 1)

    def test_status_defaults_to_one(self):
        for row in range(2, self.ws.max_row + 1):
            self.assertEqual(self.ws.cell(row, 1).value, 1)

    def test_mixed_hindi_english_line_kept_whole(self):
        self.assertEqual(self.ws["B4"].value, "भारत ने India को हराया")

    def test_freeze_and_autofilter(self):
        self.assertEqual(self.ws.freeze_panes, "A2")
        self.assertEqual(self.ws.auto_filter.ref, "A1:B4")

    def test_column_widths(self):
        self.assertEqual(self.ws.column_dimensions["A"].width, 13.0)
        self.assertEqual(self.ws.column_dimensions["B"].width, 100.0)


class TestVisibilityNewsLayout(unittest.TestCase):
    """Upper Band.xlsx / Breaking FF + Top.xlsx: A=Visibility, B=News, Arial 10."""

    @classmethod
    def setUpClass(cls):
        cls.ws = build_workbook(feed("upper_band"), HINDI_LINES, 1, "09:00:00 PM").active

    def test_sheet_name_matches_playout_software(self):
        self.assertEqual(self.ws.title, "Breaking News FF")

    def test_headers(self):
        self.assertEqual(self.ws["A1"].value, "Visibility")
        self.assertEqual(self.ws["B1"].value, "News")

    def test_header_is_yellow_but_not_bold(self):
        self.assertEqual(self.ws["A1"].fill.start_color.rgb, "FFFFFF00")
        self.assertFalse(self.ws["A1"].font.b)

    def test_arial_10_font(self):
        self.assertEqual(self.ws["B2"].font.name, "Arial")
        self.assertEqual(self.ws["B2"].font.sz, 10)

    def test_visibility_defaults_to_one(self):
        for row in range(2, self.ws.max_row + 1):
            self.assertEqual(self.ws.cell(row, 1).value, 1)

    def test_no_freeze_or_autofilter(self):
        self.assertIsNone(self.ws.freeze_panes)
        self.assertIsNone(self.ws.auto_filter.ref)

    def test_column_width(self):
        self.assertEqual(self.ws.column_dimensions["B"].width, 68.7109375)

    def test_full_screen_breaking_uses_same_layout(self):
        ws = build_workbook(feed("full_screen_breaking"), HINDI_LINES, 1, "09:00:00 PM").active
        self.assertEqual(ws.title, "Breaking News FF")
        self.assertEqual([ws["A1"].value, ws["B1"].value], ["Visibility", "News"])


class TestBreakingLtLayout(unittest.TestCase):
    """Breaking LT.xlsx: News sheet (Visibility/Category/News) + Category sheet."""

    @classmethod
    def setUpClass(cls):
        cls.wb = build_workbook(feed("breaking_news"), HINDI_LINES, 1, "09:00:00 PM")

    def test_two_sheets_in_order(self):
        self.assertEqual(self.wb.sheetnames, ["Breaking LT News", "Breaking LT Category"])

    def test_news_sheet_headers(self):
        ws = self.wb["Breaking LT News"]
        self.assertEqual(
            [ws["A1"].value, ws["B1"].value, ws["C1"].value],
            ["Visibility", "Category", "News"],
        )

    def test_category_defaults_to_9pm_when_txt_has_none(self):
        ws = self.wb["Breaking LT News"]
        for row in range(2, ws.max_row + 1):
            self.assertEqual(ws.cell(row, 2).value, dt_time(21, 0, 0))

    def test_category_uses_excel_time_number_format(self):
        self.assertEqual(
            self.wb["Breaking LT News"]["B2"].number_format, "hh:mm:ss\\ AM/PM"
        )

    def test_news_text_in_column_c(self):
        self.assertEqual(self.wb["Breaking LT News"]["C2"].value, HINDI_LINES[0])

    def test_category_sheet_lists_distinct_times_once(self):
        cat = self.wb["Breaking LT Category"]
        self.assertEqual([cat["A1"].value, cat["B1"].value], ["Visibility", "Category"])
        self.assertEqual(cat.max_row, 2)
        self.assertEqual(cat["B2"].value, dt_time(21, 0, 0))

    def test_custom_default_category_is_honoured(self):
        wb = build_workbook(feed("breaking_news"), HINDI_LINES, 1, "08:00:00 PM")
        self.assertEqual(wb["Breaking LT News"]["B2"].value, dt_time(20, 0, 0))
        self.assertEqual(wb["Breaking LT Category"]["B2"].value, dt_time(20, 0, 0))

    def test_no_lines_means_no_category_rows(self):
        wb = build_workbook(feed("breaking_news"), [], 1, "09:00:00 PM")
        self.assertEqual(wb["Breaking LT News"].max_row, 1)
        self.assertEqual(wb["Breaking LT Category"].max_row, 1)


class TestBreakingLtSplitCategory(unittest.TestCase):
    """The first N lines take the earlier slot; everything after takes the
    default, so a newly-added line always lands on the default."""

    FIVE = [f"खबर {i}" for i in range(1, 6)]

    def build(self, lines, first_time="08:00:00 PM", first_count=2):
        return build_workbook(
            feed("breaking_news"), lines, 1, "09:00:00 PM", first_time, first_count
        )

    def test_first_two_are_8pm_rest_are_9pm(self):
        ws = self.build(self.FIVE)["Breaking LT News"]
        self.assertEqual(
            [ws.cell(r, 2).value for r in range(2, 7)],
            [dt_time(20, 0), dt_time(20, 0), dt_time(21, 0), dt_time(21, 0), dt_time(21, 0)],
        )

    def test_category_sheet_lists_both_times_in_order(self):
        cat = self.build(self.FIVE)["Breaking LT Category"]
        self.assertEqual(cat.max_row, 3)
        self.assertEqual(cat["B2"].value, dt_time(20, 0))
        self.assertEqual(cat["B3"].value, dt_time(21, 0))
        self.assertEqual([cat["A2"].value, cat["A3"].value], [1, 1])

    def test_category_sheet_keeps_time_number_format(self):
        cat = self.build(self.FIVE)["Breaking LT Category"]
        self.assertEqual(cat["B2"].number_format, "hh:mm:ss\\ AM/PM")
        self.assertEqual(cat["B3"].number_format, "hh:mm:ss\\ AM/PM")

    def test_newly_added_line_gets_the_default_time(self):
        """Adding a 6th line must not shift the 8 PM block."""
        ws = self.build(self.FIVE + ["नई खबर"])["Breaking LT News"]
        self.assertEqual(ws["B2"].value, dt_time(20, 0))
        self.assertEqual(ws["B3"].value, dt_time(20, 0))
        self.assertEqual(ws["B7"].value, dt_time(21, 0))

    def test_fewer_lines_than_the_first_count(self):
        wb = self.build(["सिर्फ एक"])
        self.assertEqual(wb["Breaking LT News"]["B2"].value, dt_time(20, 0))
        cat = wb["Breaking LT Category"]
        self.assertEqual(cat.max_row, 2)
        self.assertEqual(cat["B2"].value, dt_time(20, 0))

    def test_exactly_the_first_count_yields_one_distinct_time(self):
        wb = self.build(["एक", "दो"])
        self.assertEqual(wb["Breaking LT Category"].max_row, 2)
        self.assertEqual(wb["Breaking LT Category"]["B2"].value, dt_time(20, 0))

    def test_count_zero_disables_the_split(self):
        wb = self.build(self.FIVE, first_count=0)
        ws = wb["Breaking LT News"]
        self.assertTrue(all(ws.cell(r, 2).value == dt_time(21, 0) for r in range(2, 7)))
        self.assertEqual(wb["Breaking LT Category"].max_row, 2)

    def test_identical_first_and_default_times_collapse_to_one_row(self):
        wb = self.build(self.FIVE, first_time="09:00:00 PM")
        self.assertEqual(wb["Breaking LT Category"].max_row, 2)

    def test_custom_split_time_is_honoured(self):
        ws = self.build(self.FIVE, first_time="07:30:00 AM", first_count=3)["Breaking LT News"]
        self.assertEqual(ws["B2"].value, dt_time(7, 30))
        self.assertEqual(ws["B4"].value, dt_time(7, 30))
        self.assertEqual(ws["B5"].value, dt_time(21, 0))

    def test_other_formats_ignore_the_split_settings(self):
        ws = build_workbook(
            feed("upper_band"), self.FIVE, 1, "09:00:00 PM", "08:00:00 PM", 2
        ).active
        self.assertEqual([ws["A1"].value, ws["B1"].value], ["Visibility", "News"])
        self.assertEqual(ws.max_column, 2)


class TestEmptyAndDefaults(unittest.TestCase):
    def test_every_format_still_writes_its_header_when_empty(self):
        for key in ("top_news", "upper_band", "breaking_news", "full_screen_breaking"):
            wb = build_workbook(feed(key), [], 1, "09:00:00 PM")
            ws = wb.active
            self.assertEqual(ws.max_row, 1, key)
            self.assertIsNotNone(ws["A1"].value, key)

    def test_custom_default_visibility_is_applied(self):
        ws = build_workbook(feed("upper_band"), HINDI_LINES, 0, "09:00:00 PM").active
        self.assertEqual(ws["A2"].value, 0)

    def test_unknown_format_raises(self):
        bad = Feed(
            key="x", label="X", txt_file="x.txt", excel_file="x.xlsx",
            excel_format="does_not_exist", sheet_name="S",
        )
        with self.assertRaises(UnknownFeedFormatError):
            build_workbook(bad, HINDI_LINES, 1, "09:00:00 PM")


class TestFileWriting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_writes_file_that_reloads(self):
        path = os.path.join(self.tmp, "TopNewsLT.xlsx")
        generate_feed_excel(feed("top_news"), HINDI_LINES, path, 1, "09:00:00 PM")
        ws = openpyxl.load_workbook(path).active
        self.assertEqual(ws["B2"].value, HINDI_LINES[0])

    def test_creates_missing_destination_folder(self):
        path = os.path.join(self.tmp, "nested", "deeper", "Upper Band.xlsx")
        generate_feed_excel(feed("upper_band"), HINDI_LINES, path, 1, "09:00:00 PM")
        self.assertTrue(os.path.exists(path))

    def test_leaves_no_temp_files_behind(self):
        path = os.path.join(self.tmp, "Upper Band.xlsx")
        generate_feed_excel(feed("upper_band"), HINDI_LINES, path, 1, "09:00:00 PM")
        leftovers = [n for n in os.listdir(self.tmp) if n.startswith(".~tmp_")]
        self.assertEqual(leftovers, [])

    def test_rewrite_replaces_rather_than_appends(self):
        path = os.path.join(self.tmp, "Upper Band.xlsx")
        generate_feed_excel(feed("upper_band"), HINDI_LINES, path, 1, "09:00:00 PM")
        generate_feed_excel(feed("upper_band"), ["सिर्फ एक लाइन"], path, 1, "09:00:00 PM")
        ws = openpyxl.load_workbook(path).active
        self.assertEqual(ws.max_row, 2)
        self.assertEqual(ws["B2"].value, "सिर्फ एक लाइन")

    def test_locked_file_raises_and_preserves_original(self):
        """A locked destination must raise ExcelLockedError, never corrupt the
        existing workbook the playout system is reading."""
        path = os.path.join(self.tmp, "Upper Band.xlsx")
        generate_feed_excel(feed("upper_band"), HINDI_LINES, path, 1, "09:00:00 PM")
        original_size = os.path.getsize(path)

        real_replace = os.replace

        def deny(src, dst):
            if os.path.abspath(dst) == os.path.abspath(path):
                raise PermissionError("locked by Excel")
            return real_replace(src, dst)

        os.replace = deny
        try:
            with self.assertRaises(ExcelLockedError):
                generate_feed_excel(
                    feed("upper_band"), ["नई लाइन"], path, 1, "09:00:00 PM",
                    attempts=2, base_delay=0.01,
                )
        finally:
            os.replace = real_replace

        self.assertEqual(os.path.getsize(path), original_size)
        ws = openpyxl.load_workbook(path).active
        self.assertEqual(ws["B2"].value, HINDI_LINES[0])
        self.assertEqual([n for n in os.listdir(self.tmp) if n.startswith(".~tmp_")], [])


if __name__ == "__main__":
    unittest.main()
