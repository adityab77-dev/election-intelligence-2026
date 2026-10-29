"""election-intelligence-2026.

A Python platform for election forecasting and analysis.

This top-level package is intentionally light: it exposes the package version
and nothing else, so importing it stays cheap and free of side effects. Public
functionality lives in the subpackages (``config``, ``data``, ``models``,
``llm``, ``analysis``, ``dashboard`` and ``utils``).
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
