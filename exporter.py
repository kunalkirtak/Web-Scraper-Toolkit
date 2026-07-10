"""
exporter.py
===========
Turns a list of scraped records (dataclass instances from models.py) into
CSV and/or JSON files on disk.

Kept as plain functions rather than a class: exporting is a stateless,
input-in/file-out operation with no session or config to hold between
calls, so a class here would just be ceremony. (Contrast with
`BaseScraper`, which genuinely needs to hold a session and retry config
across many calls — that's the right place for a class in this codebase.)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Sequence, Union

from config import settings
from logger import get_logger
from utils import records_to_dicts

logger = get_logger(__name__)

Record = Any  # a dataclass instance from models.py (NewsArticle/Product/JobListing)


def export_csv(records: Sequence[Record], filepath: Union[str, Path]) -> Path:
    """Write `records` to `filepath` as CSV. Column headers are taken from
    the union of keys across all records (in first-seen order), so this
    works even if some records have extra/missing optional fields.

    Writing an empty list produces a header-less, zero-row file rather
    than raising — callers can check the return value's size if they need
    to distinguish "nothing scraped" from "export failed".
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    rows = records_to_dicts(records)

    if not rows:
        logger.warning("export_csv: no records to write - creating empty file at %s", filepath)
        filepath.write_text("", encoding="utf-8")
        return filepath

    fieldnames = _ordered_fieldnames(rows)

    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Wrote %d row(s) to %s", len(rows), filepath)
    return filepath


def export_json(records: Sequence[Record], filepath: Union[str, Path]) -> Path:
    """Write `records` to `filepath` as a pretty-printed JSON array."""
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    rows = records_to_dicts(records)

    with filepath.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False, default=str)

    logger.info("Wrote %d record(s) to %s", len(rows), filepath)
    return filepath


def export_records(
    records: Sequence[Record],
    name: str,
    formats: Sequence[str] = ("csv", "json"),
    output_dir: Union[str, Path, None] = None,
) -> Dict[str, Path]:
    """Convenience wrapper: export `records` under `<output_dir>/<name>.<ext>`
    for every format in `formats`. Returns a dict mapping format -> path
    written, so callers (main.py) can report exactly what was produced.
    """
    output_dir = Path(output_dir) if output_dir else settings.output_dir
    written: Dict[str, Path] = {}

    for fmt in formats:
        fmt = fmt.lower().strip()
        target = output_dir / f"{name}.{fmt}"
        if fmt == "csv":
            written["csv"] = export_csv(records, target)
        elif fmt == "json":
            written["json"] = export_json(records, target)
        else:
            logger.warning("Unsupported export format '%s' - skipped", fmt)

    return written


def _ordered_fieldnames(rows: List[Dict[str, Any]]) -> List[str]:
    """Union of keys across all rows, preserving first-seen order, so the
    CSV header stays stable even if row 1 happens to be missing a field
    that a later row has."""
    seen: Dict[str, None] = {}
    for row in rows:
        for key in row:
            seen.setdefault(key, None)
    return list(seen.keys())


if __name__ == "__main__":
    # `python exporter.py` — round-trip a couple of dummy records through
    # both formats into a throwaway temp directory, and confirm what comes
    # back out matches what went in.
    import tempfile

    from models import Product

    sample = [
        Product(source_url="https://example.test/", name="Widget A", price=9.99, rating=4),
        Product(source_url="https://example.test/", name="Widget B", price=19.99, rating=5),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        paths = export_records(sample, name="demo_products", output_dir=tmp)
        print("Wrote:", paths)

        with open(paths["json"], encoding="utf-8") as f:
            loaded = json.load(f)
        assert len(loaded) == 2
        assert loaded[0]["name"] == "Widget A"

        with open(paths["csv"], encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        assert len(reader) == 2
        assert reader[1]["name"] == "Widget B"

    print("exporter.py self-check passed.")
