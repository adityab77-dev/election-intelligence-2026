"""Correlated Monte Carlo engine (Phase 6).

Consumes Phase 5 per-state forecast distributions and produces the Senate
control probability via correlated, seeded, vectorised simulation. Shared by
both regimes in the long run; MVP covers the pre-election regime only.
"""

from __future__ import annotations

from election_intelligence.simulate.engine import (
    MonteCarloEngine,
    SimulationConfig,
    SimulationOutput,
)

__all__ = ["MonteCarloEngine", "SimulationConfig", "SimulationOutput"]
