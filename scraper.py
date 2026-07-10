"""
scraper.py
==========
Core scraping engine.

`BaseScraper` owns everything that is *not* specific to a single target
site: session reuse, header rotation, retries with exponential backoff,
rate limiting, and turning a response into a `BeautifulSoup` tree.

Three concrete scrapers subclass it, each responsible only for knowing
*where* to look on the page and *how* to turn one HTML fragment into one
typed record from `models.py`:

    NewsScraper     -> https://news.ycombinator.com/
    ProductScraper  -> https://books.toscrape.com/
    JobScraper      -> https://realpython.github.io/fake-jobs/

Selectors were verified against each site's live HTML at the time of
writing. Sites change - that's why every parse step is wrapped so one
broken card/row is logged and skipped rather than crashing the run.
"""

from __future__ import annotations

import random
import time
from typing import Dict, List, Optional, Type
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, RequestException, Timeout

from config import settings
from logger import get_logger
from models import JobListing, NewsArticle, Product
from utils import clean_text as _clean_text
from utils import parse_int as _parse_int
from utils import parse_price as _parse_price
from utils import timed

logger = get_logger(__name__)

# books.toscrape.com encodes the star rating as a CSS class, e.g.
# <p class="star-rating Three">, instead of a plain number.
_RATING_WORDS: Dict[str, int] = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


# --------------------------------------------------------------------------- #
# Base scraper
# --------------------------------------------------------------------------- #

class BaseScraper:
    """Shared HTTP + parsing machinery for every concrete scraper.

    Responsibilities:
      * reuse a single `requests.Session` (connection pooling / keep-alive)
      * rotate User-Agent headers per request
      * retry transient failures (timeouts, connection errors, 5xx, 429)
        with exponential backoff, WITHOUT retrying permanent client errors
        like 404
      * enforce a polite delay between requests to the same host
      * hand back parsed `BeautifulSoup`, never raw text, to subclasses
    """

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self._req_cfg = settings.request

    def _headers(self) -> dict:
        return {
            "User-Agent": random.choice(self._req_cfg.user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch(self, url: str) -> Optional[BeautifulSoup]:
        """GET `url` and return parsed HTML, or None if every retry failed."""
        last_exc: Optional[Exception] = None

        for attempt in range(1, self._req_cfg.max_retries + 1):
            try:
                response = self.session.get(
                    url, headers=self._headers(), timeout=self._req_cfg.timeout
                )
                response.raise_for_status()
                # Polite pause before the caller (likely) fetches the next page.
                time.sleep(self._req_cfg.delay_between_requests)
                return BeautifulSoup(response.text, "lxml")

            except HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status is not None and status < 500 and status != 429:
                    # A 404/403/etc. won't fix itself on retry - fail fast.
                    logger.error("Non-retryable HTTP %s for %s: %s", status, url, exc)
                    return None
                last_exc = exc

            except (Timeout, RequestsConnectionError, RequestException) as exc:
                last_exc = exc

            wait = self._req_cfg.backoff_factor * (2 ** (attempt - 1))
            logger.warning(
                "Request failed (attempt %d/%d) for %s: %s - retrying in %.1fs",
                attempt, self._req_cfg.max_retries, url, last_exc, wait,
            )
            time.sleep(wait)

        logger.error(
            "Giving up on %s after %d attempts: %s",
            url, self._req_cfg.max_retries, last_exc,
        )
        return None

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "BaseScraper":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# News scraper - Hacker News front page
# --------------------------------------------------------------------------- #

class NewsScraper(BaseScraper):
    """Scrapes headline listings from Hacker News (news.ycombinator.com)."""

    def __init__(self) -> None:
        cfg = settings.news
        super().__init__(cfg.base_url)
        self.cfg = cfg

    def _page_url(self, page: int) -> str:
        if page <= 1:
            return self.base_url
        return f"{self.base_url}?{self.cfg.page_param}={page}"

    @timed
    def scrape(self, pages: Optional[int] = None) -> List[NewsArticle]:
        pages = pages or self.cfg.max_pages
        articles: List[NewsArticle] = []

        for page_num in range(1, pages + 1):
            url = self._page_url(page_num)
            logger.info("Scraping news page %d/%d: %s", page_num, pages, url)
            soup = self.fetch(url)
            if soup is None:
                logger.warning("Skipping news page %d - fetch failed", page_num)
                continue

            rows = soup.select("tr.athing")
            if not rows:
                logger.warning("No article rows found on %s - layout may have changed", url)
                continue

            for row in rows:
                try:
                    article = self._parse_row(row, source_url=url)
                    if article:
                        articles.append(article)
                except Exception as exc:  # one bad row must never kill the run
                    logger.error("Failed to parse a news row on %s: %s", url, exc)

        logger.info("News scrape complete: %d articles collected", len(articles))
        return articles

    def _parse_row(self, row, source_url: str) -> Optional[NewsArticle]:
        rank_tag = row.select_one("span.rank")
        rank = _parse_int(rank_tag.get_text()) if rank_tag else None

        title_tag = row.select_one("span.titleline > a")
        if title_tag is None:
            return None
        title = _clean_text(title_tag.get_text())
        article_url = urljoin(source_url, title_tag.get("href", ""))

        # Score / author / comment count live in the sibling "subtext" row.
        subtext = row.find_next_sibling("tr")
        points = author = comments = None
        if subtext:
            score_tag = subtext.select_one("span.score")
            points = _parse_int(score_tag.get_text()) if score_tag else None

            author_tag = subtext.select_one("a.hnuser")
            author = _clean_text(author_tag.get_text()) if author_tag else None

            for link in subtext.select("a"):
                text = _clean_text(link.get_text())
                if "comment" in text.lower():
                    comments = _parse_int(text)
                    break
                if text.lower() == "discuss":
                    comments = 0
                    break

        return NewsArticle(
            source_url=source_url,
            title=title,
            rank=rank,
            points=points,
            author=author,
            comments_count=comments,
            article_url=article_url,
        )


# --------------------------------------------------------------------------- #
# Product scraper - books.toscrape.com
# --------------------------------------------------------------------------- #

class ProductScraper(BaseScraper):
    """Scrapes book listings from books.toscrape.com (a scraping sandbox)."""

    def __init__(self) -> None:
        cfg = settings.products
        super().__init__(cfg.base_url)
        self.cfg = cfg

    def _page_url(self, page: int) -> str:
        if page <= 1:
            return self.base_url
        return urljoin(self.base_url, f"catalogue/page-{page}.html")

    @timed
    def scrape(self, pages: Optional[int] = None) -> List[Product]:
        pages = pages or self.cfg.max_pages
        products: List[Product] = []

        for page_num in range(1, pages + 1):
            url = self._page_url(page_num)
            logger.info("Scraping products page %d/%d: %s", page_num, pages, url)
            soup = self.fetch(url)
            if soup is None:
                logger.warning("Skipping products page %d - fetch failed", page_num)
                continue

            cards = soup.select("article.product_pod")
            if not cards:
                logger.warning("No product cards found on %s - layout may have changed", url)
                continue

            for card in cards:
                try:
                    product = self._parse_card(card, source_url=url)
                    if product:
                        products.append(product)
                except Exception as exc:
                    logger.error("Failed to parse a product card on %s: %s", url, exc)

        logger.info("Product scrape complete: %d products collected", len(products))
        return products

    def _parse_card(self, card, source_url: str) -> Optional[Product]:
        link_tag = card.select_one("h3 > a")
        if link_tag is None:
            return None
        name = _clean_text(link_tag.get("title") or link_tag.get_text())
        product_url = urljoin(source_url, link_tag.get("href", ""))

        price_tag = card.select_one("p.price_color")
        price = _parse_price(price_tag.get_text()) if price_tag else None

        availability_tag = card.select_one("p.instock.availability")
        availability = _clean_text(availability_tag.get_text()) if availability_tag else None

        rating_tag = card.select_one("p.star-rating")
        rating = None
        if rating_tag:
            rating_word = next(
                (c for c in rating_tag.get("class", []) if c in _RATING_WORDS), None
            )
            rating = _RATING_WORDS.get(rating_word) if rating_word else None

        return Product(
            source_url=source_url,
            name=name,
            price=price,
            currency="GBP",
            availability=availability,
            rating=rating,
            # Category only appears on the per-book detail page, not the
            # listing page - left as None here to avoid 20x the requests.
            # See JobScraper/ProductScraper docstrings in README for the
            # "fetch_detail" enhancement idea.
            category=None,
            product_url=product_url,
        )


# --------------------------------------------------------------------------- #
# Job scraper - realpython.github.io/fake-jobs
# --------------------------------------------------------------------------- #

class JobScraper(BaseScraper):
    """Scrapes vacancy cards from realpython.github.io/fake-jobs — a static,
    single-page mock job board published for scraping tutorials/exercises."""

    def __init__(self) -> None:
        cfg = settings.jobs
        super().__init__(cfg.base_url)
        self.cfg = cfg

    @timed
    def scrape(self, pages: Optional[int] = None) -> List[JobListing]:
        # `pages` is accepted so every scraper shares the same call signature
        # (main.py doesn't need to special-case this one) - fake-jobs is a
        # single static page, so it's simply ignored here.
        logger.info("Scraping jobs: %s", self.base_url)
        soup = self.fetch(self.base_url)
        if soup is None:
            logger.error("Job scrape aborted - could not fetch %s", self.base_url)
            return []

        cards = soup.select("div.card")
        if not cards:
            logger.warning("No job cards found on %s - layout may have changed", self.base_url)
            return []

        jobs: List[JobListing] = []
        for card in cards:
            try:
                job = self._parse_card(card, source_url=self.base_url)
                if job:
                    jobs.append(job)
            except Exception as exc:
                logger.error("Failed to parse a job card: %s", exc)

        logger.info("Job scrape complete: %d listings collected", len(jobs))
        return jobs

    def _parse_card(self, card, source_url: str) -> Optional[JobListing]:
        title_tag = card.select_one("h2.title")
        if title_tag is None:
            return None
        title = _clean_text(title_tag.get_text())

        company_tag = card.select_one("h3.company")
        company = _clean_text(company_tag.get_text()) if company_tag else None

        location_tag = card.select_one("p.location")
        location = _clean_text(location_tag.get_text()) if location_tag else None

        date_tag = card.select_one("time")
        date_posted = date_tag.get("datetime") if date_tag else None

        # Both "Learn" and "Apply" share class="card-footer-item"; "Apply"
        # is the one whose href points at this site's own /jobs/ detail page.
        apply_tag = card.select_one("a.card-footer-item[href*='/jobs/']")
        job_url = urljoin(source_url, apply_tag.get("href")) if apply_tag else None

        return JobListing(
            source_url=source_url,
            title=title,
            company=company,
            location=location,
            job_type=None,  # fake-jobs does not expose a job-type field
            date_posted=date_posted,
            job_url=job_url,
        )


# Registry so main.py (Part 3) can dispatch `--scraper news|products|jobs`
# without an if/elif chain.
SCRAPERS: Dict[str, Type[BaseScraper]] = {
    "news": NewsScraper,
    "products": ProductScraper,
    "jobs": JobScraper,
}


if __name__ == "__main__":
    # `python scraper.py` - quick smoke test: scrape one page from every
    # target and print the first few records of each.
    for name, scraper_cls in SCRAPERS.items():
        print(f"\n=== {name} ===")
        with scraper_cls() as scraper:
            records = scraper.scrape(pages=1)
            for record in records[:3]:
                print(record.to_dict())
            print(f"... {len(records)} total record(s)")
