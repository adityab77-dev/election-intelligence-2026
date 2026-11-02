"""Storage: DuckDB-backed persistence and querying.

Public surface:
    - :class:`Database` — the facade (client + migrations + repositories).
    - :class:`DuckDBClient` — the low-level connection wrapper.
    - :class:`Migrator`, :class:`SeedLoader` — schema and seed-data management.
    - ``entities`` and ``repositories`` modules — row models and CRUD repos.
"""

from __future__ import annotations

from election_intelligence.data.storage import entities, repositories
from election_intelligence.data.storage.database import Database
from election_intelligence.data.storage.duckdb_client import DuckDBClient
from election_intelligence.data.storage.migrations import Migrator
from election_intelligence.data.storage.seed import SeedLoader

__all__ = [
    "Database",
    "DuckDBClient",
    "Migrator",
    "SeedLoader",
    "entities",
    "repositories",
]
