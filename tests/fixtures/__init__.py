"""Shared test fixtures and sample data.

Exposes the fixtures directory path so tests can load sample files without
hard-coding paths. The synthetic "golden-path" dataset (races, units, polls) is
populated in Phase 3 once the schema exists; this package only provides the anchor.
"""

from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent

__all__ = ["FIXTURES_DIR"]
