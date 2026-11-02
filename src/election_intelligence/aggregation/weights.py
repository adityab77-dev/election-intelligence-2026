"""Poll weighting functions for the aggregation engine (Phase 4).

Three independent, pure weight components, combined multiplicatively by the
engine:

1. **Sample size** — ``sqrt(n)``, capped, so larger polls count for more with
   diminishing returns.
2. **Recency** — exponential decay by poll age with a configurable half-life.
3. **Pollster quality** — a multiplier derived from the pollster's letter grade.

No forecasting logic here — just weights.
"""

from __future__ import annotations

import math

# Pollster letter grade -> quality multiplier in (0, 1].
GRADE_SCORES: dict[str, float] = {
    "A+": 1.00,
    "A": 0.95,
    "A-": 0.90,
    "A/B": 0.85,
    "B+": 0.80,
    "B": 0.70,
    "B-": 0.60,
    "C+": 0.50,
    "C": 0.40,
    "C-": 0.30,
    "D+": 0.25,
    "D": 0.20,
    "D-": 0.15,
    "F": 0.10,
}

DEFAULT_QUALITY = 0.5
DEFAULT_SAMPLE_SIZE = 600
MAX_EFFECTIVE_N = 1500
DEFAULT_HALF_LIFE_DAYS = 14.0


def sample_size_weight(
    sample_size: int | None,
    *,
    max_effective_n: int = MAX_EFFECTIVE_N,
    default_sample_size: int = DEFAULT_SAMPLE_SIZE,
) -> float:
    """Return ``sqrt(min(n, cap))``; missing/invalid n uses a default."""
    n = sample_size if (sample_size is not None and sample_size > 0) else default_sample_size
    return math.sqrt(min(n, max_effective_n))


def recency_weight(
    age_days: float, *, half_life_days: float = DEFAULT_HALF_LIFE_DAYS
) -> float:
    """Return ``0.5 ** (age / half_life)``; a fresh poll (age 0) weighs 1.0."""
    age = max(age_days, 0.0)
    if half_life_days <= 0:
        return 1.0
    return 0.5 ** (age / half_life_days)


def quality_weight(grade: str | None, *, default: float = DEFAULT_QUALITY) -> float:
    """Map a pollster letter grade to a multiplier; unknown/missing -> default."""
    if grade is None:
        return default
    return GRADE_SCORES.get(grade.strip(), default)


__all__ = [
    "GRADE_SCORES",
    "DEFAULT_QUALITY",
    "DEFAULT_SAMPLE_SIZE",
    "MAX_EFFECTIVE_N",
    "DEFAULT_HALF_LIFE_DAYS",
    "sample_size_weight",
    "recency_weight",
    "quality_weight",
]
