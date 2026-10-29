"""Claude API integration.

Houses the client wrapper used to talk to the Claude API. Prompt templates and
higher-level narrative/analysis helpers will build on top of this client.
"""

from __future__ import annotations

from election_intelligence.llm.client import ClaudeClient

__all__ = ["ClaudeClient"]
