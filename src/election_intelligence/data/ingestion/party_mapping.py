"""Candidate -> party mapping layer (Phase A).

Wikipedia general-election poll tables label candidate columns with a party
suffix, e.g. ``Jon Ossoff (D)`` / ``Mike Collins (R)``. This layer reads that
suffix, with a small static override for any candidate column that lacks one.
"""

from __future__ import annotations

import re

from election_intelligence.data.storage.entities import Party

_SUFFIX_RE = re.compile(r"\((D|R|I|L|G)\)")
_SUFFIX_TO_PARTY = {
    "D": Party.DEM,
    "R": Party.REP,
    "I": Party.IND,
    "L": Party.LIB,
    "G": Party.GRN,
}

# Static override for candidate column headers that carry no (party) suffix.
# Keyed by a lowercase substring of the header. Extend per cycle as needed.
_CANDIDATE_OVERRIDES: dict[str, Party] = {
    "generic republican": Party.REP,
    "generic democrat": Party.DEM,
}


def party_from_header(header: str) -> Party | None:
    """Return the party for a candidate column header, or None if undetermined."""
    text = str(header).strip()
    match = _SUFFIX_RE.search(text)
    if match:
        return _SUFFIX_TO_PARTY.get(match.group(1))
    lowered = text.lower()
    for needle, party in _CANDIDATE_OVERRIDES.items():
        if needle in lowered:
            return party
    return None


def candidate_name(header: str) -> str:
    """Strip the party suffix and footnotes from a candidate column header."""
    text = _SUFFIX_RE.sub("", str(header))
    text = re.sub(r"\[[^\]]*\]", "", text)
    return re.sub(r"\s+", " ", text).strip()


__all__ = ["party_from_header", "candidate_name"]
