"""Optional read-only MCP server (outside the critical path).

Exposes a few read-only tools over the DuckDB file (current control odds, state
table, conditional scenario, explain last change) so the live model can be queried
from Claude Desktop. If it breaks, the forecast keeps running. No logic yet.
"""

from __future__ import annotations

__all__: list[str] = []
