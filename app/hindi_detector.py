"""Devanagari (Hindi) text detection helpers."""
import re

DEVANAGARI_PATTERN = re.compile(r"[ऀ-ॿ]")


def contains_devanagari(text: str) -> bool:
    """Return True if text contains at least one Devanagari (U+0900-U+097F) character."""
    if not text:
        return False
    return bool(DEVANAGARI_PATTERN.search(text))


def filter_hindi_lines(lines):
    """Given an iterable of text lines, return only the lines that contain Devanagari text,
    with surrounding whitespace stripped and empty lines removed. Order is preserved.
    """
    result = []
    for line in lines:
        stripped = (line or "").strip()
        if not stripped:
            continue
        if contains_devanagari(stripped):
            result.append(stripped)
    return result
