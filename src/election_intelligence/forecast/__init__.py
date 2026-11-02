"""Pre-election forecasting regime (Phase 5 — Senate Forecast Engine).

Combines the Phase 4 polling average with a fundamentals prior into a per-state
margin distribution (``mu``, ``sigma``) plus named drivers, handling RCV/runoff/
independent special cases. Kept deliberately separate from poll aggregation.
Deterministic; no LLM. No logic implemented yet.
"""

from __future__ import annotations

__all__: list[str] = []
