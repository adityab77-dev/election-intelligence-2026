"""Narrative layer (Phase 11 — Claude narration).

Turns the structured attribution record into plain-English prose via a single
constrained Claude call, with a hard validator gate: every numeric token in the
output must match the record, and certainty words are rejected. No logic yet.
"""

from __future__ import annotations

__all__: list[str] = []
