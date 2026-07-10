"""
models.py
=========
Typed data models for every record the toolkit can scrape.

Using `dataclasses` here (instead of raw dicts) buys us several things
that matter for a "production-ready" portfolio piece:

  * Type hints on every field, so IDEs/mypy catch mistakes early
  * `__post_init__` validation, so a malformed scrape fails loudly at the
    point of creation instead of silently producing a blank CSV row
  * A single `to_dict()` used consistently by both the CSV and JSON
    exporters, so adding a field to a model automatically flows through
    to both export formats with no exporter changes required
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utc_now_iso() -> str:
    """Timestamp helper, isolated so tests can monkeypatch it if needed."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class BaseRecord:
    """Common fields every scraped record carries, regardless of type."""

    source_url: str
    scraped_at: str = field(default_factory=_utc_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        """Flatten this record into a plain dict, ready for csv.DictWriter
        or json.dumps."""
        return asdict(self)


@dataclass
class NewsArticle(BaseRecord):
    """A single headline scraped from a news listing page."""

    title: str = ""
    rank: Optional[int] = None
    points: Optional[int] = None
    author: Optional[str] = None
    comments_count: Optional[int] = None
    article_url: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("NewsArticle requires a non-empty title")
        self.title = self.title.strip()


@dataclass
class Product(BaseRecord):
    """A single catalog item scraped from an e-commerce listing page."""

    name: str = ""
    price: Optional[float] = None
    currency: str = "GBP"
    availability: Optional[str] = None
    rating: Optional[int] = None          # normalized to 1-5
    category: Optional[str] = None
    product_url: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Product requires a non-empty name")
        self.name = self.name.strip()
        if self.price is not None and self.price < 0:
            raise ValueError(f"Product price cannot be negative: {self.price}")
        if self.rating is not None and not (0 <= self.rating <= 5):
            raise ValueError(f"Product rating must be within 0-5: {self.rating}")


@dataclass
class JobListing(BaseRecord):
    """A single vacancy scraped from a job board listing page."""

    title: str = ""
    company: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None        # e.g. "Full-time", "Internship"
    date_posted: Optional[str] = None
    job_url: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.title or not self.title.strip():
            raise ValueError("JobListing requires a non-empty title")
        self.title = self.title.strip()


# Convenience alias used by exporter.py / main.py so new record types only
# need to be registered in one place.
RECORD_TYPES = {
    "news": NewsArticle,
    "products": Product,
    "jobs": JobListing,
}


if __name__ == "__main__":
    # `python models.py` — quick sanity check that each model behaves.
    article = NewsArticle(source_url="https://news.ycombinator.com/", title="  Show HN: Cool Thing  ", rank=1, points=120)
    book = Product(source_url="https://books.toscrape.com/", name="A Light in the Attic", price=51.77, rating=3)
    job = JobListing(source_url="https://realpython.github.io/fake-jobs/", title="Python Developer", company="Payne, Roberts and Davis")

    for record in (article, book, job):
        print(type(record).__name__, "->", record.to_dict())
