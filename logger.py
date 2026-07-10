"""
logger.py
=========
Application-wide logging setup.

Every module that wants to log calls `get_logger(__name__)` and gets back a
`logging.Logger` that:

  * writes to `logs/scraper.log`, rotating automatically at ~5 MB so the
    log file never grows unbounded during long-running or repeated scrapes
  * mirrors the same messages to the console, colorized by level when the
    optional `colorlog` package is available (falls back gracefully if not)
  * is safe to call multiple times for the same name without duplicating
    handlers (a common source of "why is every line logged twice?" bugs)
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

try:
    import colorlog

    _HAS_COLORLOG = True
except ImportError:  # colorlog is a "nice to have", never a hard dependency
    _HAS_COLORLOG = False


def _build_file_handler() -> RotatingFileHandler:
    handler = RotatingFileHandler(
        filename=settings.logging.log_file,
        maxBytes=settings.logging.max_bytes,
        backupCount=settings.logging.backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    return handler


def _build_console_handler() -> logging.StreamHandler:
    handler = logging.StreamHandler(stream=sys.stdout)

    if _HAS_COLORLOG:
        formatter = colorlog.ColoredFormatter(
            fmt="%(log_color)s" + _LOG_FORMAT,
            datefmt=_DATE_FORMAT,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )
    else:
        formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    handler.setFormatter(formatter)
    return handler


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for `name` (typically `__name__`).

    Safe to call repeatedly - handlers are only attached once per logger
    name, even if `get_logger` is called from multiple modules/imports.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured (e.g. this module was imported more than
        # once under the same name) - reuse it as-is.
        return logger

    level = getattr(logging, settings.logging.log_level.upper(), logging.INFO)
    logger.setLevel(level)

    logger.addHandler(_build_file_handler())
    logger.addHandler(_build_console_handler())

    # Prevent messages from bubbling up to the root logger and printing
    # a second time.
    logger.propagate = False

    return logger


if __name__ == "__main__":
    # `python logger.py` — quick smoke test of every log level.
    log = get_logger("logger.selftest")
    log.debug("Debug message (only visible if LOG_LEVEL=DEBUG)")
    log.info("Info message - normal operation")
    log.warning("Warning message - something worth a second look")
    log.error("Error message - a request or parse step failed")
    log.critical("Critical message - the scraper cannot continue")
