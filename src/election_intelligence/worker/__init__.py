"""The worker: the single writer.

Owns the scheduler (event-driven + debounce + backstop) and the pipeline that runs
the five steps on every tick (fetch, project, simulate, compare, alert), writing
exactly one ``runs`` row per tick. The dashboard and optional MCP server only read.
No logic implemented yet.
"""

from __future__ import annotations

__all__: list[str] = []
