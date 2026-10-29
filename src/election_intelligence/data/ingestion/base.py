"""Abstract interface for data sources.

Every ingestion source implements :class:`DataSource`, returning a normalised
``pandas.DataFrame``. Keeping a single contract here means the storage layer
and tests can treat all sources uniformly.

No concrete sources are implemented yet; this defines the contract only.
"""

from __future__ import annotations

import abc

import pandas as pd


class DataSource(abc.ABC):
    """A readable, normalisable source of election-related data."""

    #: Short, stable identifier for the source (e.g. ``"polls"``).
    name: str

    @abc.abstractmethod
    def fetch(self) -> pd.DataFrame:
        """Read the source and return a normalised DataFrame.

        Raises:
            election_intelligence.exceptions.IngestionError: if the source
                cannot be read or parsed.
        """
        raise NotImplementedError
