"""Entry point for Taaza News Excel Sync."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import Config
from app.logger import setup_logger
from app.single_instance import SingleInstance

# Distinct from the older single-workbook app's folder so both can be
# installed and run side by side without sharing config.json or sync.db.
APPDATA_FOLDER = "TaazaNewsExcelSync"


def _show_already_running():
    """Tell the user why the second copy closed. The --windowed build has no
    console, so without this the double-click would appear to do nothing."""
    try:
        from tkinter import Tk, messagebox

        root = Tk()
        root.withdraw()
        messagebox.showinfo(
            "Taaza News Excel Sync",
            "Taaza News Excel Sync is already running.\n\n"
            "Only one copy can run at a time, because two copies would "
            "overwrite each other's Excel files.",
        )
        root.destroy()
    except Exception:  # noqa: BLE001 - never let the notice itself crash startup
        pass


def main():
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller EXE: keep config/logs in a per-user writable
        # location, not next to the executable (which may sit in Program Files,
        # read-only for standard users after a proper installer) and not inside
        # the temporary --onefile extraction directory.
        base_dir = os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")), APPDATA_FOLDER
        )
        os.makedirs(base_dir, exist_ok=True)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    logger = setup_logger(base_dir)
    logger.info("Application started")

    # Two instances would both rebuild the same four workbooks and overwrite
    # each other's output in the live Excel folder.
    guard = SingleInstance()
    if guard.already_running:
        logger.warning("Another instance is already running - exiting")
        _show_already_running()
        return

    config_path = os.path.join(base_dir, "config.json")
    first_run = not os.path.exists(config_path)
    config = Config(config_path, base_dir=base_dir)
    if first_run:
        config.save()

    os.makedirs(config.txt_root, exist_ok=True)
    os.makedirs(config.excel_root, exist_ok=True)

    from app.gui import run_app

    try:
        run_app(config)
    finally:
        guard.release()


if __name__ == "__main__":
    main()
