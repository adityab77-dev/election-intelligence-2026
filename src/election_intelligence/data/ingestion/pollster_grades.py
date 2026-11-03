"""Static pollster-grade lookup table (Phase A).

Wikipedia poll tables carry no pollster quality grades. Since the 538 ratings
feed is dead (see REAL_POLL_INTEGRATION_PLAN.md), this ships an approximate,
last-known letter grade per common pollster so the aggregation engine keeps its
pollster-quality weighting. Unknown pollsters return None -> the aggregation
engine's existing neutral default weight applies.

These grades are approximate (derived from publicly reported ratings) and are a
V1 stopgap; a licensed ratings source would replace them. Lookup is done on a
canonicalized (lowercased, de-noised) pollster name.
"""

from __future__ import annotations

import re

# Canonical (lowercased) pollster name -> approximate letter grade.
_GRADES: dict[str, str] = {
    "siena college": "A+",
    "the new york times/siena college": "A+",
    "nyt/siena": "A+",
    "selzer & co.": "A+",
    "marquette university law school": "A",
    "marist college": "A",
    "monmouth university": "A",
    "abc news/the washington post": "A",
    "quinnipiac university": "A-",
    "suffolk university": "A-",
    "fox news": "A-",
    "surveyusa": "A-",
    "muhlenberg college": "A-",
    "university of georgia": "A-",
    "emerson college": "B+",
    "yougov": "B+",
    "data for progress": "B",
    "echelon insights": "B",
    "insideradvantage": "B",
    "cygnal": "B",
    "atlasintel": "B",
    "morning consult": "B",
    "public policy polling": "B",
    "research co.": "B",
    "co/efficient": "B",
    "noble predictive insights": "B",
    "tipp insights": "B-",
    "quantus insights": "C+",
    "wpa intelligence": "C+",
    "trafalgar group": "C+",
    "rmg research": "C+",
    "tyson group": "C",
    "victory insights": "C",
}

_FOOTNOTE_RE = re.compile(r"\[[^\]]*\]")
_LEAN_RE = re.compile(r"\((?:D|R|I)\)")


def _canonical(pollster: str) -> str:
    text = _FOOTNOTE_RE.sub("", str(pollster))
    text = _LEAN_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def grade_for(pollster: str) -> str | None:
    """Return an approximate letter grade for a pollster, or None if unknown."""
    return _GRADES.get(_canonical(pollster))


__all__ = ["grade_for"]
