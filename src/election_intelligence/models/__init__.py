"""Forecasting models.

This package defines the model *interface* only. Concrete forecasting logic
(statsmodels-based estimators, aggregation, simulation) is deliberately left
unimplemented at this stage.
"""

from __future__ import annotations

from election_intelligence.models.base import ForecastModel

__all__ = ["ForecastModel"]
