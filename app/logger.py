"""Rotating file logging setup."""
import logging
import os
from logging.handlers import RotatingFileHandler

LOGGER_NAME = "taaza_news_excel_sync"
MAX_BYTES = 2 * 1024 * 1024
BACKUP_COUNT = 5


def setup_logger(base_dir):
    """Configure the application logger to write to base_dir/logs/app.log."""
    logs_dir = os.path.join(base_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    handler = RotatingFileHandler(
        os.path.join(logs_dir, "app.log"),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%d-%m-%Y %H:%M:%S")
    )
    logger.addHandler(handler)
    return logger
