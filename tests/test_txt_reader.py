import codecs
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.txt_reader import (
    TxtReadError,
    clean_and_extract_hindi_lines,
    decode_text_bytes,
    extract_hindi_lines,
    extract_hindi_message,
    remove_bitmap_tags,
)


class TestBitmapRemoval(unittest.TestCase):
    """Spec section 35: automated BITMAP tests."""

    def test_1_trailing_bitmap_removed(self):
        text = "आज बड़ी खबर है <BITMAP>:\\newsair\\logo.psd</BITMAP>"
        self.assertEqual(clean_and_extract_hindi_lines(text), ["आज बड़ी खबर है"])

    def test_2_bitmap_in_middle_removed_and_spaces_cleaned(self):
        text = "आज बड़ी खबर है <BITMAP>abc.psd</BITMAP> और यह महत्वपूर्ण है।"
        self.assertEqual(
            clean_and_extract_hindi_lines(text), ["आज बड़ी खबर है और यह महत्वपूर्ण है।"]
        )

    def test_3_bitmap_only_line_ignored(self):
        text = "<BITMAP>:\\newsair\\logo.psd</BITMAP>"
        self.assertEqual(clean_and_extract_hindi_lines(text), [])

    def test_4_mixed_hindi_english_kept_whole(self):
        text = "भारत ने India को हराया <BITMAP>:\\newsair\\logo.psd</BITMAP>"
        self.assertEqual(clean_and_extract_hindi_lines(text), ["भारत ने India को हराया"])

    def test_5_english_only_with_bitmap_kept(self):
        text = "India won the match <BITMAP>:\\newsair\\logo.psd</BITMAP>"
        self.assertEqual(clean_and_extract_hindi_lines(text), ["India won the match"])

    def test_6_multiple_lines_each_own_bitmap(self):
        text = "पहली खबर <BITMAP>a.psd</BITMAP>\nदूसरी खबर <BITMAP>b.psd</BITMAP>"
        self.assertEqual(clean_and_extract_hindi_lines(text), ["पहली खबर", "दूसरी खबर"])

    def test_multiple_bitmaps_same_line(self):
        text = "आज की बड़ी खबर <BITMAP>abc.psd</BITMAP> सामने आई <BITMAP>xyz.psd</BITMAP>"
        self.assertEqual(clean_and_extract_hindi_lines(text), ["आज की बड़ी खबर सामने आई"])

    def test_bitmap_at_start_of_line(self):
        text = "<BITMAP>:\\newsair\\logo.psd</BITMAP> कोलकाता में बड़ा हादसा"
        self.assertEqual(clean_and_extract_hindi_lines(text), ["कोलकाता में बड़ा हादसा"])

    def test_case_insensitive_tag(self):
        text = "आज बड़ी खबर <bitmap>x.psd</bitmap> है और <Bitmap>y.psd</Bitmap> रहेगी"
        self.assertEqual(clean_and_extract_hindi_lines(text), ["आज बड़ी खबर है और रहेगी"])

    def test_bitmap_metadata_never_leaks_as_content(self):
        text = "खबर <BITMAP>:\\newsair\\logo.psd</BITMAP>"
        result = clean_and_extract_hindi_lines(text)
        joined = "\n".join(result)
        for forbidden in ("newsair", "logo.psd", "BITMAP", "psd"):
            self.assertNotIn(forbidden, joined)

    def test_preserves_line_order_and_boundaries(self):
        text = (
            "पहली खबर <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
            "दूसरी खबर <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
            "तीसरी खबर <BITMAP>:\\newsair\\logo.psd</BITMAP>"
        )
        self.assertEqual(
            clean_and_extract_hindi_lines(text), ["पहली खबर", "दूसरी खबर", "तीसरी खबर"]
        )


class TestFullExampleFromSpec(unittest.TestCase):
    """Spec section 17: complete worked example."""

    def test_complete_processing_example(self):
        text = (
            "राष्ट्रीय मंदिर के पास इलाके में भीषण आग <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
            "A major fire occurred near the temple.\n"
            "दर्शनार्थियों की भीड़ में अचानक मौत <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
            "The crowd suddenly faced a tragedy.\n"
            "7 श्रद्धालुओं की मौत, 12 से अधिक लोग घायल <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
            "Seven people died and many were injured.\n"
            "भारत ने India के साथ नई बातचीत शुरू की <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
            "India started a new discussion.\n"
            "<BITMAP>:\\newsair\\logo.psd</BITMAP>"
        )
        expected = [
            "राष्ट्रीय मंदिर के पास इलाके में भीषण आग",
            "A major fire occurred near the temple.",
            "दर्शनार्थियों की भीड़ में अचानक मौत",
            "The crowd suddenly faced a tragedy.",
            "7 श्रद्धालुओं की मौत, 12 से अधिक लोग घायल",
            "Seven people died and many were injured.",
            "भारत ने India के साथ नई बातचीत शुरू की",
            "India started a new discussion.",
        ]
        self.assertEqual(clean_and_extract_hindi_lines(text), expected)


class TestEncodingFallback(unittest.TestCase):
    def test_utf8_bom(self):
        raw = codecs.BOM_UTF8 + "आज बड़ी खबर है।".encode("utf-8")
        self.assertEqual(decode_text_bytes(raw), "आज बड़ी खबर है।")

    def test_plain_utf8(self):
        raw = "आज बड़ी खबर है।".encode("utf-8")
        self.assertEqual(decode_text_bytes(raw), "आज बड़ी खबर है।")

    def test_utf16_le_bom(self):
        raw = "आज बड़ी खबर है।".encode("utf-16")
        self.assertEqual(decode_text_bytes(raw), "आज बड़ी खबर है।")

    def test_cp1252_fallback(self):
        raw = "Hello café".encode("cp1252")
        self.assertEqual(decode_text_bytes(raw), "Hello café")

    def test_latin1_last_resort_never_raises(self):
        raw = bytes([0xFF, 0xFE, 0x00, 0x81, 0x82])
        result = decode_text_bytes(raw)
        self.assertIsInstance(result, str)


class TestExtractFromFile(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="txt_reader_test_")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _write(self, name, content, encoding="utf-8"):
        path = os.path.join(self.tmp_dir, name)
        with open(path, "w", encoding=encoding, newline="") as f:
            f.write(content)
        return path

    def test_extract_hindi_lines_from_real_file(self):
        path = self._write(
            "row_02.txt",
            "राष्ट्रीय मंदिर के पास इलाके में भीषण आग <BITMAP>:\\newsair\\logo.psd</BITMAP>\n"
            "A major fire occurred near the temple.\n"
            "7 श्रद्धालुओं की मौत, 12 से अधिक लोग घायल <BITMAP>:\\newsair\\logo.psd</BITMAP>\n",
        )
        lines = extract_hindi_lines(path)
        self.assertEqual(lines, [
            "राष्ट्रीय मंदिर के पास इलाके में भीषण आग",
            "A major fire occurred near the temple.",
            "7 श्रद्धालुओं की मौत, 12 से अधिक लोग घायल",
        ])

    def test_extract_hindi_message_joined(self):
        path = self._write("row_01.txt", "पहली खबर <BITMAP>a.psd</BITMAP>\nदूसरी खबर <BITMAP>b.psd</BITMAP>\n")
        self.assertEqual(extract_hindi_message(path), "पहली खबर\nदूसरी खबर")

    def test_english_only_file_kept(self):
        path = self._write("row_09.txt", "Today is an important news story.\nThe government made an announcement.\n")
        self.assertEqual(
            extract_hindi_lines(path),
            ["Today is an important news story.", "The government made an announcement."],
        )
        self.assertEqual(
            extract_hindi_message(path),
            "Today is an important news story.\nThe government made an announcement.",
        )

    def test_missing_file_raises(self):
        with self.assertRaises(TxtReadError):
            extract_hindi_lines(os.path.join(self.tmp_dir, "does_not_exist.txt"))

    def test_bom_file_extracts_correctly(self):
        path = os.path.join(self.tmp_dir, "row_05.txt")
        with open(path, "wb") as f:
            f.write(codecs.BOM_UTF8 + "आज देश में बड़ी खबर आई है।<BITMAP>x.psd</BITMAP>".encode("utf-8"))
        self.assertEqual(extract_hindi_lines(path), ["आज देश में बड़ी खबर आई है।"])


if __name__ == "__main__":
    unittest.main()
