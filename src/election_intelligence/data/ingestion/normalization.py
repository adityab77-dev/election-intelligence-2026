"""Normalization helpers for parsed poll rows (Phase A).

Pure functions that turn the messy text of Wikipedia poll tables into the
typed values the ``Poll`` entity expects. No I/O, no forecasting logic.
"""

from __future__ import annotations

import re
from datetime import date

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

_VALID_POPULATIONS = {"LV", "RV", "A", "V"}

_FOOTNOTE_RE = re.compile(r"\[[^\]]*\]")
_LEAN_RE = re.compile(r"\((?:D|R|I)\)")
_YEAR_RE = re.compile(r"(\d{4})")
_PCT_RE = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
_SIZE_RE = re.compile(r"([\d,]{2,})")
_POP_RE = re.compile(r"\(([A-Za-z]{1,2})\)")
_MONTH_DAY_RE = re.compile(r"([A-Za-z]+)\.?\s+(\d{1,2})(?:,\s*(\d{4}))?$")
_DAY_RE = re.compile(r"(\d{1,2})(?:,\s*(\d{4}))?$")


def clean_pollster(text: str) -> str:
    """Strip footnote markers and partisan-lean tags from a 'Poll source' cell."""
    cleaned = _FOOTNOTE_RE.sub("", str(text))
    cleaned = _LEAN_RE.sub("", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_pct(text: object) -> float | None:
    """Extract a percentage like '48%' or '48.5%'; returns None for '—'/NaN."""
    match = _PCT_RE.search(str(text))
    return float(match.group(1)) if match else None


def parse_sample(text: object) -> tuple[int | None, str | None]:
    """Parse '2,500 (LV)' -> (2500, 'LV'); population normalized to LV/RV/A/V."""
    raw = str(text)
    population: str | None = None
    pop_match = _POP_RE.search(raw)
    if pop_match:
        candidate = pop_match.group(1).upper()
        if candidate in _VALID_POPULATIONS:
            population = candidate
    size_match = _SIZE_RE.search(raw)
    size = int(size_match.group(1).replace(",", "")) if size_match else None
    return size, population


def _parse_one(part: str, fallback_month: int | None, fallback_year: int | None):
    """Return (month, day, year) from a date fragment, using fallbacks."""
    text = part.strip().rstrip(",").strip()
    md = _MONTH_DAY_RE.match(text)
    if md:
        month = _MONTHS.get(md.group(1).lower())
        year = int(md.group(3)) if md.group(3) else fallback_year
        return month, int(md.group(2)), year
    d = _DAY_RE.match(text)
    if d:
        year = int(d.group(2)) if d.group(2) else fallback_year
        return fallback_month, int(d.group(1)), year
    return None


def _to_date(parts) -> date | None:
    if not parts or parts[0] is None or parts[2] is None:
        return None
    try:
        return date(parts[2], parts[0], parts[1])
    except ValueError:
        return None


def parse_date_range(text: str) -> tuple[date | None, date | None]:
    """Parse a Wikipedia 'Date(s) administered' cell to (start, end) dates.

    Handles 'May 16-17, 2026', 'April 28 - May 2, 2026', 'November 2, 2026',
    'through October 20, 2026', with en/em dashes and footnote markers.
    """
    cleaned = str(text).replace("–", "-").replace("—", "-").strip()
    cleaned = _FOOTNOTE_RE.sub("", cleaned).strip()
    cleaned = re.sub(r"^through\s+", "", cleaned, flags=re.IGNORECASE).strip()

    year_match = _YEAR_RE.search(cleaned)
    year = int(year_match.group(1)) if year_match else None

    fragments = [p.strip() for p in cleaned.split("-") if p.strip()]
    if not fragments:
        return None, None

    if len(fragments) == 1:
        end = _parse_one(fragments[0], None, year)
        return _to_date(end), _to_date(end)

    start = _parse_one(fragments[0], None, year)
    start_month = start[0] if start else None
    end = _parse_one(fragments[-1], start_month, year)
    if start and start[2] is None:
        start = (start[0], start[1], year)
    return _to_date(start), _to_date(end)


__all__ = [
    "clean_pollster",
    "parse_pct",
    "parse_sample",
    "parse_date_range",
]
