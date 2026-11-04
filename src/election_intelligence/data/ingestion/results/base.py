"""Pluggable election-results source contract (Phase E)."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field

from election_intelligence.data.storage.entities import ElectionResult, ReportingSnapshot


@dataclass
class RaceResults:
    """A race-level snapshot plus its per-candidate detail rows."""

    snapshot: ReportingSnapshot
    candidates: list[ElectionResult] = field(default_factory=list)


class ResultsSource(abc.ABC):
    """A source of real election results, yielding one ``RaceResults`` per race.

    Implementations fetch from an external source (Wikipedia now; DDHQ/SoS later)
    and normalise to ``ReportingSnapshot`` + ``ElectionResult``. They do not touch
    the database — the caller passes the result to ``ResultsIngestor``.
    """

    #: Short, stable identifier (e.g. ``"wikipedia"``).
    name: str

    @abc.abstractmethod
    def fetch(self) -> list[RaceResults]:
        """Fetch and normalise current results (empty list if none reported)."""
        raise NotImplementedError


__all__ = ["ResultsSource", "RaceResults"]
