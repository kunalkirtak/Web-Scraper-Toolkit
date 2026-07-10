"""
utils.py
========
Small, generic helpers shared across the toolkit. Nothing in this module
knows about a specific target site (that belongs in scraper.py) or about
records (that belongs in models.py) — just text cleaning, number parsing,
timing, and list utilities that any scraper or the CLI might need.
"""

from __future__ import annotations

import re
import time
from dataclasses import asdict, is_dataclass
from functools import wraps
from typing import Any, Callable, Dict, Iterable, List, Optional, TypeVar

from logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


# --------------------------------------------------------------------------- #
# Text / number parsing
# --------------------------------------------------------------------------- #

def clean_text(value: Optional[str]) -> str:
    """Collapse whitespace/newlines from scraped HTML text into one tidy
    string. Returns "" for None/empty input instead of raising."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def parse_price(raw: Optional[str]) -> Optional[float]:
    """Extract a float from a price string like '£53.74' or '$1,299.00'.
    Returns None if no numeric portion is found."""
    if not raw:
        return None
    match = re.search(r"[\d,]+\.?\d*", raw)
    if not match:
        return None
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None


def parse_int(raw: Optional[str]) -> Optional[int]:
    """Pull the first integer out of a string like '128 points' or '1,024'.
    Returns None if no digits are found."""
    if not raw:
        return None
    match = re.search(r"\d+", raw.replace(",", ""))
    return int(match.group()) if match else None


# --------------------------------------------------------------------------- #
# List / record utilities
# --------------------------------------------------------------------------- #

def deduplicate(records: List[T], key: Callable[[T], Any]) -> List[T]:
    """Drop later records that share a key with one already seen, preserving
    the order of first occurrence. Useful when re-running a scraper appends
    to a file that may already contain a given item (e.g. same product_url
    scraped twice across overlapping pages)."""
    seen: set = set()
    unique: List[T] = []
    dropped = 0

    for record in records:
        record_key = key(record)
        if record_key in seen:
            dropped += 1
            continue
        seen.add(record_key)
        unique.append(record)

    if dropped:
        logger.info("Deduplicated %d record(s) (%d unique remain)", dropped, len(unique))

    return unique


def records_to_dicts(records: Iterable[Any]) -> List[Dict[str, Any]]:
    """Normalize a list of dataclass records (or already-plain dicts) into
    plain dicts, so exporters never need to care which one they were given."""
    result = []
    for record in records:
        if is_dataclass(record) and not isinstance(record, type):
            result.append(asdict(record))
        elif isinstance(record, dict):
            result.append(record)
        else:
            raise TypeError(
                f"Expected a dataclass instance or dict, got {type(record).__name__}"
            )
    return result


# --------------------------------------------------------------------------- #
# Timing helpers
# --------------------------------------------------------------------------- #

def format_duration(seconds: float) -> str:
    """Format a duration in seconds as a short human-readable string,
    e.g. 245.2 -> '4m 5s', 3.1 -> '3.1s'."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}m {secs}s"


def timed(func: Callable[..., T]) -> Callable[..., T]:
    """Decorator that logs how long the wrapped function took to run.
    Used on scraper.scrape() calls so the CLI summary and logs both show
    per-target timing without cluttering the scraping logic itself."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            logger.debug("%s took %s", func.__qualname__, format_duration(elapsed))

    return wrapper


if __name__ == "__main__":
    # `python utils.py` — quick sanity check of each helper.
    assert clean_text("  hello \n world  ") == "hello world"
    assert parse_price("£53.74") == 53.74
    assert parse_price("$1,299.00") == 1299.00
    assert parse_price("Free") is None
    assert parse_int("128 points") == 128
    assert parse_int("1,024 comments") == 1024
    assert format_duration(3.14) == "3.1s"
    assert format_duration(125) == "2m 5s"
    print("All utils.py self-checks passed.")
