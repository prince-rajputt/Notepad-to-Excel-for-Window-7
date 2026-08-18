"""Final end-to-end test for the News Data / News Category Excel design,
driven through the real watchdog-based watcher (not by calling sync_engine
methods directly)."""
import os
import shutil
import sys
import time

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROJECT_ROOT)

from openpyxl import load_workbook

from app.config import Config
from app.database import Database
from app.sync_engine import SyncEngine
from app.watcher import FolderWatcher

BASE = os.path.join(PROJECT_ROOT, "tests", "manual", "_e2e_workspace")
TXT_ROOT = os.path.join(BASE, "notepad")
EXCEL_PATH = os.path.join(TXT_ROOT, "All_Content.xlsx")
DB_PATH = os.path.join(TXT_ROOT, "sync.db")

WAIT = 4.5  # debounce (1.5s) + stability checks (~2.5s) + margin


def write_txt(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def dump_state(label):
    db = Database(DB_PATH)
    print(f"\n--- {label} ---")
    for rec in db.get_all():
        print(f"row {rec.row_number} | {rec.category} | {rec.file_name} | {len(rec.news_lines)} lines")
    db.close()
    if os.path.exists(EXCEL_PATH):
        wb = load_workbook(EXCEL_PATH)
        ws = wb["News Data"]
        print("News Data rows:")
        for row in ws.iter_rows(min_row=2, values_only=True):
            print(" ", row[0], "|", row[1], "|", repr(row[2]))


def main():
    if os.path.exists(BASE):
        shutil.rmtree(BASE)
    os.makedirs(TXT_ROOT)

    config = Config(os.path.join(BASE, "e2e_config.json"))
    config.txt_root = TXT_ROOT
    config.excel_file = EXCEL_PATH
    config.database_file = DB_PATH
    config.save()

    db = Database(DB_PATH)
    engine = SyncEngine(db, config)
    engine.on_event = lambda msg: print(f"[EVENT] {msg}")

    # Step 1: initial scan of a folder that already has row_02, row_03
    write_txt(
        os.path.join(TXT_ROOT, "row_02.txt"),
        "आज देश में महत्वपूर्ण खबर आई है। <BITMAP>a.psd</BITMAP>\n"
        "Important news has arrived.\n"
        "सरकार ने नई घोषणा की है। <BITMAP>a.psd</BITMAP>\n",
    )
    write_txt(os.path.join(TXT_ROOT, "row_03.txt"), "बंगाल की खबर <BITMAP>a.psd</BITMAP>")
    engine.run_initial_scan()
    dump_state("After initial scan (row_02=खबर India x2 lines, row_03=खबर बंगाल x1 line)")

    watcher = FolderWatcher(engine)
    watcher.start()
    print("Watcher started.")

    # Step 2: add a new TXT file (row_08 -> Entertainment)
    write_txt(os.path.join(TXT_ROOT, "row_08.txt"), "नई फिल्म रिलीज होने वाली है। <BITMAP>a.psd</BITMAP>")
    time.sleep(WAIT)
    dump_state("After adding row_08.txt (expect Entertainment category, 1 news line)")

    # Step 3: modify row_02.txt - old news must be replaced, not duplicated
    write_txt(
        os.path.join(TXT_ROOT, "row_02.txt"),
        "अपडेटेड खबर एक। <BITMAP>a.psd</BITMAP>\n"
        "अपडेटेड खबर दो। <BITMAP>a.psd</BITMAP>\n"
        "अपडेटेड खबर तीन। <BITMAP>a.psd</BITMAP>\n",
    )
    time.sleep(WAIT)
    dump_state("After modifying row_02.txt (expect 3 NEW news lines replacing the old 2, no duplicates)")

    # Step 4: delete row_03.txt - its news AND placeholder must vanish entirely
    os.remove(os.path.join(TXT_ROOT, "row_03.txt"))
    time.sleep(WAIT)
    dump_state("After deleting row_03.txt (expect खबर बंगाल fully gone from Excel - live mirror)")

    # Step 5: recreate row_03.txt
    write_txt(os.path.join(TXT_ROOT, "row_03.txt"), "बंगाल की नई खबर <BITMAP>a.psd</BITMAP>")
    time.sleep(WAIT)
    dump_state("After recreating row_03.txt (expect खबर बंगाल back with fresh content)")

    watcher.stop()
    db.close()
    print("\nWatcher stopped. E2E script complete.")


if __name__ == "__main__":
    main()
