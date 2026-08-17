"""Load/save config.json."""
import json
import os

from app.row_mapping import DEFAULT_ROW_CATEGORIES

DEFAULT_TXT_ROOT = os.path.join(os.path.expanduser("~"), "Documents", "notepad")

DEFAULT_CONFIG = {
    "txt_root": DEFAULT_TXT_ROOT,
    "excel_file": os.path.join(DEFAULT_TXT_ROOT, "All_Content.xlsx"),
    "database_file": os.path.join(DEFAULT_TXT_ROOT, "sync.db"),
    "watch_extensions": [".txt"],
    "keep_deleted_records": True,
    "auto_start": False,
    "mapping_password": "2001",
    "row_categories": dict(DEFAULT_ROW_CATEGORIES),
}


class Config:
    def __init__(self, path):
        self.path = path
        self.data = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
        self.load()

    def load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                self.data.update(loaded)
            except (json.JSONDecodeError, OSError):
                pass
        return self.data

    def save(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    @property
    def txt_root(self):
        return self.data["txt_root"]

    @txt_root.setter
    def txt_root(self, value):
        self.data["txt_root"] = value

    @property
    def excel_file(self):
        return self.data["excel_file"]

    @excel_file.setter
    def excel_file(self, value):
        self.data["excel_file"] = value

    @property
    def database_file(self):
        return self.data["database_file"]

    @database_file.setter
    def database_file(self, value):
        self.data["database_file"] = value

    # -- row/category mapping -------------------------------------------------

    @property
    def row_categories(self):
        return self.data.setdefault("row_categories", dict(DEFAULT_ROW_CATEGORIES))

    def get_category(self, row_number):
        return self.row_categories.get(str(row_number), "Unassigned")

    def set_category(self, row_number, category_name):
        self.row_categories[str(row_number)] = category_name
