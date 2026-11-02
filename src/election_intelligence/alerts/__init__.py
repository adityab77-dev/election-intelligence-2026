"""Alerting layer.

Threshold rules (P1-P3/Info) with deduplication, batching, and two-run
confirmation, delivered to Slack with optional phone push. Includes the
stale-worker alarm. No logic implemented yet.
"""

from __future__ import annotations

__all__: list[str] = []
