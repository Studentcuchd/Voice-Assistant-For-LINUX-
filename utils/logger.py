"""Logging configuration for the voice assistant."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    DIM = "\033[2m"


class ColoredFormatter(logging.Formatter):
    LEVEL_COLORS = {
        logging.DEBUG: Colors.DIM + Colors.WHITE,
        logging.INFO: Colors.CYAN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.BOLD + Colors.RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, Colors.RESET)
        original_levelname = record.levelname
        original_message = record.msg
        record.levelname = f"{color}{record.levelname:<8}{Colors.RESET}"
        record.msg = f"{color}{record.msg}{Colors.RESET}"
        try:
            return super().format(record)
        finally:
            record.levelname = original_levelname
            record.msg = original_message


def setup_logger(name: str = "voice_assistant", log_level: int = logging.DEBUG, log_dir: str = "logs") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        ColoredFormatter(fmt="%(asctime)s  %(levelname)s  %(message)s", datefmt="%H:%M:%S")
    )
    logger.addHandler(console_handler)

    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, f"assistant_{datetime.now():%Y%m%d}.log")
    file_handler = RotatingFileHandler(
        log_filename,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  [%(module)s:%(lineno)d]  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)

    logger.debug("Logger '%s' initialised -> %s", name, log_filename)
    return logger


_root_logger: logging.Logger | None = None


def get_logger(name: str = "voice_assistant") -> logging.Logger:
    global _root_logger
    if _root_logger is None:
        _root_logger = setup_logger()
    if name == "voice_assistant":
        return _root_logger
    return _root_logger.getChild(name)
