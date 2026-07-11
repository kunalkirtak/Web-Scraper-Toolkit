# Web Scraper Toolkit

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-active-brightgreen)

A modular, production-style **multi-target web scraping toolkit** built with
`requests` + `BeautifulSoup`. Unlike a single-script scraping demo, this repo
is organized the way a real internal data-collection tool would be: typed
data models, centralized configuration, rotating file logs, retry/backoff
on network calls, and dual CSV/JSON export — all driven from one CLI
entry point.

It ships with three ready-to-run scrapers targeting sites that are safe and
appropriate for scraping practice:

| Scraper    | Target                                                              | What it collects                          |
|------------|----------------------------------------------------------------------|--------------------------------------------|
| `news`     | [Hacker News](https://news.ycombinator.com/)                        | Rank, title, points, author, comment count |
| `products` | [books.toscrape.com](https://books.toscrape.com/) (scraping sandbox) | Name, price, rating, availability, category|
| `jobs`     | [realpython.github.io/fake-jobs](https://realpython.github.io/fake-jobs/) (mock job board) | Title, company, location, job type |

> **Note on targets:** `books.toscrape.com` and `fake-jobs` are static sites
> published specifically for people to practice scraping against. Hacker
> News' front page is plain server-rendered HTML with a permissive
> `robots.txt` for its listing pages. The toolkit itself is target-agnostic —
> swap in any URL via `config.py` and the same architecture applies.

---

## Table of Contents

- [Why this project](#why-this-project)
- [Features](#features)
- [Project structure](#project-structure)
- [Tech stack](#tech-stack)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Sample output](#sample-output)
- [Architecture & design decisions](#architecture--design-decisions)
- [Error handling & logging](#error-handling--logging)
- [Putting this on GitHub](#putting-this-on-github)
- [Roadmap](#roadmap)
- [Ethical scraping notice](#ethical-scraping-notice)
- [Contributing](#contributing)
- [License](#license)

---

## Why this project

Most scraping demos are a single `requests.get()` + `BeautifulSoup` script
that dies the moment a page structure changes or a request times out. This
project is built to demonstrate software-engineering habits that carry over
into any data pipeline or backend role:

- **Separation of concerns** — config, logging, models, scraping logic, and
  export logic each live in their own module.
- **Typed, validated data** — every scraped record is a `dataclass`, not a
  loose dict, so bad data fails fast and loudly.
- **Resilience** — automatic retries with exponential backoff, timeouts, and
  rotating User-Agents so a single flaky request doesn't kill the run.
- **Observability** — structured, rotating logs instead of scattered
  `print()` statements.
- **Reusability** — adding a fourth scraper means adding one config block,
  one dataclass, and one method — not rewriting the pipeline.

## Features

- [x] `requests.Session()` reuse with custom headers and rotating User-Agents
- [x] `BeautifulSoup` (via `lxml` parser) for fast, tolerant HTML parsing
- [x] Three independent scrapers: **News**, **Products**, **Jobs**
- [x] Retry logic with exponential backoff on transient network errors
- [x] Polite rate-limiting between requests to the same host
- [x] Full type hints across all modules
- [x] `dataclasses` with validation for every scraped record type
- [x] Centralized, environment-overridable configuration (`.env` support)
- [x] Rotating file logs + colorized console logs
- [x] CSV **and** JSON export for every scraper
- [x] Clean CLI entry point (`main.py`) with argparse
- [x] `.gitignore`, `requirements.txt`, MIT `LICENSE`

## Project structure

```
Web-Scraper-Toolkit/
│
├── README.md              # You are here
├── requirements.txt       # Pinned dependencies
├── .gitignore
├── LICENSE
│
├── config.py               # Centralized, env-overridable settings
├── logger.py                # Rotating file + colorized console logging
├── models.py                 # Dataclasses: NewsArticle, Product, JobListing
├── scraper.py                 # BaseScraper + NewsScraper/ProductScraper/JobScraper
├── exporter.py                 # CSV / JSON export utilities
├── utils.py                     # Shared helpers (parsing, cleaning, retries)
├── main.py                       # CLI entry point
│
├── output/                # Live-run output ( original generated output files and images)
│   ├── .gitkeep
│   ├── list_packages.png / debug_logs.png / json_output.png / all_scrapper.png
│   ├── news.csv / news.json / news.png
│   ├── products.csv / products.json / products.png
│   └── jobs.csv / jobs.json / jobs.png
│
├── samples/                # Committed, ready-to-browse sample data
│   ├── news.csv / news.json
│   ├── products.csv / products.json
│   └── jobs.csv / jobs.json
│
├── logs/
│   └── scraper.log        # Rotating application log (git-ignored)
│
└── notebooks/
    └── Demo.ipynb          # Interactive walkthrough of the toolkit
```

Every module in the tree above is implemented and tested — see
[Sample output](#sample-output) for what a real run produces.

## Tech stack

- **Python 3.10+**
- [`requests`](https://docs.python-requests.org/) — HTTP session management
- [`beautifulsoup4`](https://www.crummy.com/software/BeautifulSoup/) + `lxml` — HTML parsing
- [`python-dotenv`](https://pypi.org/project/python-dotenv/) — local environment config
- [`colorlog`](https://pypi.org/project/colorlog/) — readable console logs
- [`pandas`](https://pandas.pydata.org/) — quick post-scrape analysis (see `notebooks/Demo.ipynb`)
- [`tqdm`](https://github.com/tqdm/tqdm) — progress bars for multi-page scrapes

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/kunalkirtak/Web-Scraper-Toolkit.git
cd Web-Scraper-Toolkit

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

## Configuration

All defaults live in [`config.py`](./config.py) and can be overridden without
touching code by creating a `.env` file in the project root:

```dotenv
# .env (optional — sensible defaults are used if this file is absent)
LOG_LEVEL=INFO
SCRAPER_TIMEOUT=10
SCRAPER_MAX_RETRIES=3
SCRAPER_BACKOFF=0.6
SCRAPER_DELAY=1.0

NEWS_MAX_PAGES=2
PRODUCTS_MAX_PAGES=3
```

## Usage

```bash
# Run a single scraper and export to both CSV and JSON
python main.py --scraper news --pages 2 --format csv json

# Run every scraper in one go
python main.py --scraper all

# Run with verbose (debug-level) logging
python main.py --scraper products --pages 3 --log-level DEBUG
```

Each run prints a summary table (records scraped, time taken, files
written per target), writes timestamped log entries to `logs/scraper.log`,
and drops result files into `output/<scraper_name>.csv` / `.json`. Exit
code is `0` if at least one record was scraped across all requested
targets, `1` if every target came back empty — handy for CI/cron.

## Sample output

The [`samples/`](./samples) directory ships with real output — six CSV/JSON
files produced by running the actual `scraper.py` → `exporter.py` pipeline
against verified data from each target (the current Hacker News front page,
and the stable books.toscrape.com / fake-jobs catalogs). Browse them
directly, or open `notebooks/Demo.ipynb` for a guided walkthrough.

`samples/products.json` (first record):

```json
{
  "source_url": "https://books.toscrape.com/",
  "scraped_at": "2026-07-08T10:10:42+00:00",
  "name": "A Light in the Attic",
  "price": 51.77,
  "currency": "GBP",
  "availability": "In stock",
  "rating": 3,
  "category": null,
  "product_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
}
```

Running `python main.py` yourself writes fresh output into `output/`
(git-ignored, since it's per-run data) rather than overwriting `samples/`.

## Architecture & design decisions

**Why dataclasses instead of dicts?**
A dict typo (`"pric"` instead of `"price"`) silently produces `None` deep in
an export step. A dataclass field typo is a `TypeError` at the point the
record is created — the failure happens where the bug actually is.

**Why a `BaseRecord` base class?**
`source_url` and `scraped_at` are common to every record type. Putting them
in one place means every exporter can rely on those two fields always being
present, regardless of which scraper produced the record.

**Why per-scraper config dataclasses instead of one flat config?**
Frozen, grouped dataclasses (`NewsScraperConfig`, `ProductScraperConfig`,
`JobScraperConfig`) make it obvious which settings belong to which scraper,
and `frozen=True` prevents a scraper from accidentally mutating shared
config mid-run.

**Why retries with exponential backoff?**
Real-world scraping hits transient failures — a slow server, a dropped
connection, a rate limit. A fixed retry-then-fail approach either gives up
too early or hammers the server too fast. Exponential backoff spaces out
retries so the toolkit is resilient without being abusive to the target site.

## Error handling & logging

- Every network call is wrapped in `try/except` targeting specific
  `requests` exceptions (`Timeout`, `ConnectionError`, `HTTPError`) rather
  than a bare `except:`; unexpected exceptions are logged with full context
  before the scraper moves on to the next page/item instead of crashing the
  whole run.
- All parsing steps that can fail (a missing HTML element, an unexpected
  price format) are defensive — a single malformed listing is skipped and
  logged, not fatal to the run.
- Logs rotate at 5 MB (3 backups kept) so `logs/scraper.log` never grows
  unbounded, and every log line is timestamped, leveled, and attributed to
  the module that emitted it.

## Putting this on GitHub

```bash
# From the project root
git init
git add .
git commit -m "Initial commit: Web Scraper Toolkit"

git branch -M main
git remote add origin https://github.com/kunalkirtak/Web-Scraper-Toolkit.git
git push -u origin main
```

A few things worth checking before you push:

- Confirm `.gitignore` is doing its job: `git status` shouldn't show
  `output/*.csv`, `output/*.json`, `logs/*.log`, or `__pycache__/`.
- `samples/` is **not** git-ignored on purpose — it's the checked-in
  reference data that makes the repo useful to browse without cloning
  and running it first.
- Update the `git clone` URL in the [Installation](#installation) section
  and the copyright name in [`LICENSE`](./LICENSE) to match your GitHub
  username before publishing.
- If you want the badges at the top of this file to reflect a real CI run
  instead of being static, wiring up the GitHub Actions workflow in the
  [Roadmap](#roadmap) is the natural next step.

## Roadmap

Planned enhancements beyond this build:

- [ ] `asyncio` + `aiohttp` variant for concurrent multi-page scraping
- [ ] Pagination auto-detection instead of a fixed `max_pages`
- [ ] Optional proxy rotation support
- [ ] Wrap the toolkit as a `FastAPI` service (`POST /scrape/{target}`)
- [ ] Dockerfile for one-command reproducible runs
- [ ] `pytest` suite with `responses`-mocked HTTP for offline testing
- [ ] Scheduled runs via GitHub Actions, committing fresh CSV/JSON snapshots

## Ethical scraping notice

This toolkit is built for educational and portfolio purposes. It targets
sites that are either explicitly built for scraping practice
(`books.toscrape.com`, `fake-jobs`) or that serve plain, publicly accessible
HTML with a permissive `robots.txt` for the pages scraped. Before pointing
this toolkit at a new target, always check that site's `robots.txt` and
Terms of Service, and keep request rates polite (`SCRAPER_DELAY` exists for
exactly this reason).

## Contributing

Issues and PRs are welcome. If you're extending this for your own portfolio,
feel free to fork it — see [Roadmap](#roadmap) for ideas that would make good
follow-up commits.

## License

Distributed under the [MIT License](./LICENSE).
