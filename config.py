"""
config.py
=========
Centralized configuration for the Web Scraper Toolkit.

Every tunable value used by the scrapers (target URLs, timeouts, retry
behaviour, output paths, logging behaviour) lives here so that:

  * scraper.py / exporter.py / main.py never hard-code "magic values"
  * behaviour can be tweaked for a demo/interview walkthrough without
    touching scraping logic
  * sensitive or environment-specific values (e.g. a proxy URL) can be
    supplied via a local .env file and overridden per machine

Design notes
------------
Settings are grouped into small, frozen (immutable) dataclasses instead of
one giant config blob. This keeps each scraper's configuration self
contained and makes it obvious, at a glance, which settings belong to
which part of the toolkit.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Load variables from a local .env file (if present) into os.environ.
# This never overwrites variables that are already set in the real
# environment (e.g. in CI), which is the safer default.
load_dotenv()


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

BASE_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = BASE_DIR / "output"
LOG_DIR: Path = BASE_DIR / "logs"

# Make sure these exist even on a fresh clone of the repo.
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _env_int(name: str, default: int) -> int:
    """Read an int from the environment, falling back to `default` on
    missing/invalid values instead of raising at import time."""
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


# --------------------------------------------------------------------------- #
# Shared HTTP settings
# --------------------------------------------------------------------------- #

#: Rotated per-request so a single scrape run doesn't hammer a target with
#: one obviously-scripted User-Agent string.
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) "
    "Gecko/20100101 Firefox/126.0",
]


@dataclass(frozen=True)
class RequestConfig:
    """Controls how `scraper.py` talks to the network."""

    timeout: int = _env_int("SCRAPER_TIMEOUT", 10)          # seconds
    max_retries: int = _env_int("SCRAPER_MAX_RETRIES", 3)
    backoff_factor: float = _env_float("SCRAPER_BACKOFF", 0.6)
    # Polite delay between consecutive requests to the *same* host.
    delay_between_requests: float = _env_float("SCRAPER_DELAY", 1.0)
    user_agents: List[str] = field(default_factory=lambda: USER_AGENTS)


@dataclass(frozen=True)
class NewsScraperConfig:
    """Target: Hacker News front page (static HTML, scrape-friendly,
    no login/paywall, widely used as a public scraping example)."""

    name: str = "news"
    base_url: str = "https://news.ycombinator.com/"
    # HN paginates via ?p=2, ?p=3, ...
    page_param: str = "p"
    max_pages: int = _env_int("NEWS_MAX_PAGES", 2)


@dataclass(frozen=True)
class ProductScraperConfig:
    """Target: books.toscrape.com — a sandbox site built specifically for
    practicing scraping, so it's safe to hit repeatedly while developing."""

    name: str = "products"
    base_url: str = "https://books.toscrape.com/"
    max_pages: int = _env_int("PRODUCTS_MAX_PAGES", 3)


@dataclass(frozen=True)
class JobScraperConfig:
    """Target: realpython.github.io/fake-jobs — a static mock job board
    published by Real Python for scraping tutorials/exercises."""

    name: str = "jobs"
    base_url: str = "https://realpython.github.io/fake-jobs/"
    max_pages: int = 1  # the fake-jobs site is a single static page


@dataclass(frozen=True)
class LoggingConfig:
    log_file: Path = LOG_DIR / "scraper.log"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    max_bytes: int = 5 * 1024 * 1024   # rotate at 5 MB
    backup_count: int = 3


@dataclass(frozen=True)
class Settings:
    """Single import-friendly entry point: `from config import settings`."""

    request: RequestConfig = field(default_factory=RequestConfig)
    news: NewsScraperConfig = field(default_factory=NewsScraperConfig)
    products: ProductScraperConfig = field(default_factory=ProductScraperConfig)
    jobs: JobScraperConfig = field(default_factory=JobScraperConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    output_dir: Path = OUTPUT_DIR


settings = Settings()


if __name__ == "__main__":
    # Quick sanity check: `python config.py` prints the resolved settings.
    import pprint

    pprint.pprint(settings)
