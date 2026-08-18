"""Read .txt files and extract Hindi (Devanagari) content, stripping
<BITMAP>...</BITMAP> image-placeholder tags first.

The source files are plain Windows Notepad .txt exports where each line is
either a news line (possibly followed by a <BITMAP>...</BITMAP> path
placeholder that must never be treated as content) or plain English
commentary that should be discarded.
"""
import codecs
import logging
import re

from app.errors import DocumentReadError
from app.hindi_detector import contains_devanagari

logger = logging.getLogger("word_to_excel_sync")

BITMAP_PATTERN = re.compile(r"<BITMAP>.*?</BITMAP>", re.IGNORECASE | re.DOTALL)
WHITESPACE_RUN = re.compile(r"[ \t]+")


class TxtReadError(DocumentReadError):
    """Raised when a .txt file cannot be opened or decoded."""


def remove_bitmap_tags(text):
    """Remove every <BITMAP>...</BITMAP> section (case-insensitive) from text."""
    return BITMAP_PATTERN.sub("", text)


def clean_and_extract_hindi_lines(text):
    """Remove BITMAP tags, then return the ordered list of cleaned lines that
    contain at least one Devanagari character. English-only lines (and lines
    that were nothing but a BITMAP placeholder) are dropped. The remaining
    text is never translated, summarized, or reworded - only BITMAP removal
    and whitespace cleanup are applied.
    """
    text_without_bitmap = remove_bitmap_tags(text)
    lines = text_without_bitmap.splitlines()

    result = []
    for line in lines:
        cleaned = WHITESPACE_RUN.sub(" ", line).strip()
        if not cleaned:
            continue
        if contains_devanagari(cleaned):
            result.append(cleaned)
    return result


# Spec-named alias: identical behavior, different name for callers that
# think of the output as "news lines" rather than generic "Hindi lines".
clean_and_extract_news_lines = clean_and_extract_hindi_lines


def _looks_like_utf16_without_bom(raw_bytes):
    """Heuristic: UTF-16 text with mostly-ASCII content has a null byte in
    roughly every other position. Without this guard, blindly attempting a
    UTF-16 decode on arbitrary bytes frequently "succeeds" with garbage
    instead of raising, which would prevent the cp1252/latin-1 fallbacks
    from ever being reached.
    """
    if len(raw_bytes) < 4 or len(raw_bytes) % 2 != 0:
        return False
    null_count = raw_bytes.count(0)
    return null_count > len(raw_bytes) * 0.3


def decode_text_bytes(raw_bytes):
    """Decode raw file bytes to text with a robust encoding fallback chain:
    UTF-8 (with/without BOM) -> UTF-16 (with/without BOM) -> Windows-1252 ->
    latin-1 (never fails, used as an absolute last resort).
    """
    if raw_bytes.startswith(codecs.BOM_UTF8):
        try:
            return raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            pass

    if raw_bytes.startswith(codecs.BOM_UTF16_LE) or raw_bytes.startswith(codecs.BOM_UTF16_BE):
        try:
            return raw_bytes.decode("utf-16")
        except UnicodeDecodeError:
            pass

    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        pass

    if _looks_like_utf16_without_bom(raw_bytes):
        try:
            return raw_bytes.decode("utf-16")
        except UnicodeDecodeError:
            pass

    try:
        return raw_bytes.decode("cp1252")
    except UnicodeDecodeError:
        pass

    return raw_bytes.decode("latin-1", errors="replace")


def extract_hindi_lines(file_path):
    """Read a .txt file and return the ordered list of Hindi-only lines,
    with all <BITMAP>...</BITMAP> placeholders removed."""
    try:
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
    except OSError as exc:
        raise TxtReadError(f"Failed to open .txt file: {file_path} ({exc})") from exc

    try:
        text = decode_text_bytes(raw_bytes)
    except Exception as exc:  # noqa: BLE001 - any decoding failure must not crash the app
        raise TxtReadError(f"Failed to decode .txt content: {file_path} ({exc})") from exc

    return clean_and_extract_hindi_lines(text)


def extract_hindi_message(file_path):
    """Return the Hindi Message string (lines joined by \\n) for a .txt file."""
    return "\n".join(extract_hindi_lines(file_path))
