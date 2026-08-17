"""Data model for a tracked row_XX.txt file record."""
from dataclasses import dataclass
from typing import Optional

STATUS_ACTIVE = "Active"
STATUS_DELETED = "Deleted"


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
    deleted_at: Optional[str]
    status: str
    last_synced_at: str

    @property
    def serial_number(self):
        """The row number IS the permanent, user-facing Excel serial number."""
        return self.row_number

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
            deleted_at=row["deleted_at"],
            status=row["status"],
            last_synced_at=row["last_synced_at"],
        )
