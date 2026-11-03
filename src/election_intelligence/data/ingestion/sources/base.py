"""The pluggable poll-source contract (Phase A)."""

from __future__ import annotations

import abc

from election_intelligence.data.storage.entities import Poll


class PollSource(abc.ABC):
    """A source of real polls that yields ``Poll`` entities.

    Implementations fetch from an external source (Wikipedia now; DDHQ later)
    and return normalized ``Poll`` objects. They do not touch the database —
    the caller passes the result to the existing ``PollIngestor``.
    """

    #: Short, stable identifier (e.g. ``"wikipedia"``).
    name: str

    @abc.abstractmethod
    def fetch(self) -> list[Poll]:
        """Fetch and normalize the current polls.

        Raises:
            election_intelligence.exceptions.IngestionError: if the source
                cannot be retrieved or parsed.
        """
        raise NotImplementedError


__all__ = ["PollSource"]
