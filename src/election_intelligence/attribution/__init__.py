"""Change attribution.

Decomposes each move in P(control) into named per-state (and per-source) drivers
via single-pass sequential swap re-simulation, so contributions sum to the total
move. Consumed by the narrative and dashboard change-log layers. No logic yet.
"""

from __future__ import annotations

__all__: list[str] = []
