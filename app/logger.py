"""Rotating file + console logging setup."""
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR_NAME = "logs"
LOG_FILE_NAME = "app.log"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 5


def setup_logger(base_dir=None, level=logging.INFO):
    """Configure and return the shared 'word_to_excel_sync' logger.

    base_dir defaults to the project root (parent of this app/ package).
    """
    if base_dir is None:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    log_dir = os.path.join(base_dir, LOG_DIR_NAME)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, LOG_FILE_NAME)

    logger = logging.getLogger("word_to_excel_sync")
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%d-%m-%Y %H:%M:%S"
    )

    file_handler = RotatingFileHandler(
        log_path, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
