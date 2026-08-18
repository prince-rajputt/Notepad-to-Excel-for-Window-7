"""Data model for a tracked row_XX.txt file record.

There is no soft-delete/Status concept here: a record's existence in the
database IS its existence in the monitored folder (the Excel output is a
live mirror of the current folder, not a history).
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class FileRecord:
    id: Optional[int]
    row_number: int
    category: str
    file_name: str
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
        """The individual Hindi news lines extracted from this file, in order."""
        return self.content.split("\n") if self.content else []

    @classmethod
    def from_row(cls, row):
        return cls(
            id=row["id"],
            row_number=row["row_number"],
            category=row["category"],
            file_name=row["file_name"],
            full_path=row["full_path"],
            content=row["content"],
            file_hash=row["file_hash"],
            size=row["size"],
            mtime=row["mtime"],
            created_at=row["created_at"],
            modified_at=row["modified_at"],
            last_synced_at=row["last_synced_at"],
        )
