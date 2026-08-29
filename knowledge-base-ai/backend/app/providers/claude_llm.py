"""Anthropic Claude LLM adapter stub (T064).

This module satisfies the LLMProvider ABC so the provider factory can
instantiate it via ``LLM_PROVIDER=claude`` in .env.  All methods raise
``NotImplementedError`` with clear setup instructions until a real
implementation is added.

To activate:
    1. ``pip install anthropic``
    2. Set ``CLAUDE_API_KEY=<your-key>`` in backend/.env
    3. Set ``LLM_MODEL=claude-3-5-sonnet-20241022`` (or another model)
    4. Replace the ``NotImplementedError`` bodies below with real API calls.
"""
from __future__ import annotations

from collections.abc import AsyncIterator  # retained for return type annotation

from app.providers.base import LLMProvider

_SETUP_MSG = (
    "Claude LLM adapter is not yet configured. "
    "To enable it: (1) pip install anthropic, "
    "(2) set CLAUDE_API_KEY in backend/.env, "
    "(3) set LLM_MODEL to the desired Claude model name "
    "(e.g. claude-3-5-sonnet-20241022), "
    "(4) implement the method bodies in claude_llm.py."
)


class ClaudeLLMProvider(LLMProvider):
    """Stub adapter for Anthropic Claude models.

    Raises ``NotImplementedError`` on every call to signal that the adapter
    has not been wired up with a real API key and implementation yet.
    """

    async def generate(self, prompt: str, context: str = "") -> str:
        """Generate a complete response via the Claude Messages API.

        Raises
        ------
        NotImplementedError
            Until the adapter is fully implemented.
        """
        raise NotImplementedError(_SETUP_MSG)

    async def stream(self, prompt: str, context: str = "") -> AsyncIterator[str]:
        """Stream a response token-by-token via the Claude Messages API.

        Raises
        ------
        NotImplementedError
            Until the adapter is fully implemented.
        """
        raise NotImplementedError(_SETUP_MSG)

    @property
    def model_version(self) -> str:
        """Return the configured Claude model name.

        Raises
        ------
        NotImplementedError
            Until the adapter is fully implemented.
        """
        raise NotImplementedError(_SETUP_MSG)
