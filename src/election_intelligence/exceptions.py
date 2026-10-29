"""Project-wide exception hierarchy.

A single base class (:class:`ElectionIntelligenceError`) lets callers catch
every application-raised error with one ``except`` while still allowing
fine-grained handling of specific failures. Subpackages raise the most
specific subclass that applies.
"""

from __future__ import annotations


class ElectionIntelligenceError(Exception):
    """Base class for all errors raised by this platform."""


class ConfigurationError(ElectionIntelligenceError):
    """Raised when configuration is missing or invalid."""


class DataError(ElectionIntelligenceError):
    """Base class for data-layer failures (ingestion, storage, validation)."""


class IngestionError(DataError):
    """Raised when a data source cannot be read or parsed."""


class StorageError(DataError):
    """Raised when a database operation fails."""


class ValidationError(DataError):
    """Raised when data fails a schema or integrity check."""


class ModelError(ElectionIntelligenceError):
    """Raised when a forecasting model cannot be fit or evaluated."""


class LLMError(ElectionIntelligenceError):
    """Raised when a Claude API interaction fails."""
