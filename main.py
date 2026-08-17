"""Entry point for TXT Row to Excel Sync."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import Config
from app.logger import setup_logger


def main():
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller EXE: keep config/logs next to the executable,
        # not inside the temporary --onefile extraction directory.
        base_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    logger = setup_logger(base_dir)
    logger.info("Application started")

    config_path = os.path.join(base_dir, "config.json")
    first_run = not os.path.exists(config_path)
    config = Config(config_path)
    if first_run:
        config.save()

    os.makedirs(config.txt_root, exist_ok=True)

    from app.gui import run_app

    run_app(config)


if __name__ == "__main__":
    main()
