"""Correlated Monte Carlo engine (Phase 6).

Shared by both regimes: turns per-state margin distributions into chamber-control
probabilities via a correlated factor error structure, seeded per run for exact
replay. Produces control probability, seat histogram, paths, and conditionals.
Pure, vectorised, no LLM. No logic implemented yet.
"""

from __future__ import annotations

__all__: list[str] = []
