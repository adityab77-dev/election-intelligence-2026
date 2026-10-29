"""Wrapper around the Anthropic Claude API client.

Centralising construction of the ``anthropic.Anthropic`` client keeps API-key
handling and model defaults in one place and makes the LLM layer trivial to
mock in tests. The underlying SDK is imported lazily so that importing this
module (and the package as a whole) never requires network access or a key.

Message-construction and higher-level helpers are deferred; this provides the
authenticated client only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from election_intelligence.config import get_settings
from election_intelligence.exceptions import ConfigurationError
from election_intelligence.utils import get_logger

if TYPE_CHECKING:
    from anthropic import Anthropic

logger = get_logger(__name__)


class ClaudeClient:
    """Lazily-constructed, configured Claude API client."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str | None = None,
    ) -> None:
        settings = get_settings().claude

        resolved_key = api_key
        if resolved_key is None and settings.api_key is not None:
            resolved_key = settings.api_key.get_secret_value()
        if not resolved_key:
            raise ConfigurationError(
                "No Claude API key configured. Set EI_CLAUDE__API_KEY in the "
                "environment or pass api_key explicitly."
            )

        self._api_key = resolved_key
        self._model = model or settings.model
        self._max_retries = settings.max_retries
        self._timeout = settings.timeout_seconds
        self._client: Anthropic | None = None

    @property
    def model(self) -> str:
        """The default model id used for requests."""
        return self._model

    @property
    def client(self) -> Anthropic:
        """Return the underlying Anthropic SDK client, creating it on demand."""
        if self._client is None:
            from anthropic import Anthropic

            self._client = Anthropic(
                api_key=self._api_key,
                max_retries=self._max_retries,
                timeout=self._timeout,
            )
            logger.debug("initialised Claude client (model=%s)", self._model)
        return self._client
