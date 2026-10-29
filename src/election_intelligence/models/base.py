"""Abstract interface for forecasting models.

A common contract lets the analysis layer, the dashboard and tests treat every
estimator the same way regardless of the underlying technique. Concrete models
will subclass :class:`ForecastModel` and implement ``fit`` and ``predict``.

Intentionally no forecasting logic lives here yet — contract only.
"""

from __future__ import annotations

import abc

import pandas as pd


class ForecastModel(abc.ABC):
    """Base class for all election forecasting models."""

    #: Short, stable identifier for the model (e.g. ``"baseline-ols"``).
    name: str

    @abc.abstractmethod
    def fit(self, data: pd.DataFrame) -> ForecastModel:
        """Fit the model to training data and return ``self``.

        Raises:
            election_intelligence.exceptions.ModelError: if fitting fails.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def predict(self, data: pd.DataFrame) -> pd.DataFrame:
        """Produce forecasts for the given input rows.

        Raises:
            election_intelligence.exceptions.ModelError: if called before the
                model has been fit, or if prediction fails.
        """
        raise NotImplementedError
