"""Data model for a tracked feed source file.

There is no soft-delete/Status concept here: a record's existence in the
database IS its source .txt file's existence on disk (each workbook is a
live mirror of its own .txt file, not a history).
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class FeedRecord:
    id: Optional[int]
    feed_key: str
    label: str
    txt_file: str
    full_path: str
    content: str
    file_hash: str
    size: int
    mtime: float
    created_at: str
    modified_at: str
    last_synced_at: str

    @property
    def news_lines(self):
        """The individual news lines extracted from this file, in order."""
        return self.content.split("\n") if self.content else []

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            feed_key=row["feed_key"],
            label=row["label"],
            txt_file=row["txt_file"],
            full_path=row["full_path"],
            content=row["content"],
            file_hash=row["file_hash"],
            size=row["size"],
            mtime=row["mtime"],
            created_at=row["created_at"],
            modified_at=row["modified_at"],
            last_synced_at=row["last_synced_at"],
        )
