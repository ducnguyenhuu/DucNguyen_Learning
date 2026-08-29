"""Ollama HTTP API LLM provider.

Communicates with the Ollama server to generate text responses using the
configured ``LLM_MODEL`` (default: ``phi3.5:3.8b-mini-instruct-q4_K_M``).

The Ollama API is called with ``stream=True`` by default to support token
streaming via WebSocket.  The blocking ``generate()`` method simply collects
all streamed tokens and returns the concatenated result.

Dependencies
-----------
- ``httpx`` for async HTTP (already in requirements.txt)
- Ollama running at ``LLM_BASE_URL`` (default: http://localhost:11434)
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings
from app.core.exceptions import ModelUnavailableError
from app.core.logging import get_logger
from app.providers.base import LLMProvider

log = get_logger(__name__)

# Ollama API path for chat completions
_OLLAMA_GENERATE_PATH = "/api/generate"

# System prompt injected before every context/query
_SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions based solely on the "
    "provided document context. If the context does not contain enough "
    "information to answer the question, say so clearly. "
    "Always cite the source document when possible."
)


class LocalLLMProvider(LLMProvider):
    """Ollama HTTP API implementation of :class:`LLMProvider`.

    Communicates with Ollama's ``/api/generate`` endpoint.  Each call
    includes:

    - A system instruction
    - The retrieved document context (if non-empty)
    - The user's question
    """

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        context_window: int | None = None,
        temperature: float | None = None,
    ) -> None:
        self._model = model or settings.llm_model
        self._base_url = (base_url or settings.llm_base_url).rstrip("/")
        self._context_window = context_window or settings.llm_context_window
        self._temperature = temperature if temperature is not None else settings.llm_temperature

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, prompt: str, context: str) -> str:
        """Combine system instruction, context chunks, and user question."""
        parts: list[str] = [_SYSTEM_PROMPT]
        if context.strip():
            parts.append(f"\n\n### Relevant Document Context\n{context}")
        parts.append(f"\n\n### Question\n{prompt}")
        return "\n".join(parts)

    def _request_body(self, full_prompt: str, stream: bool) -> dict[str, Any]:
        return {
            "model": self._model,
            "prompt": full_prompt,
            "stream": stream,
            "options": {
                "temperature": self._temperature,
                "num_ctx": self._context_window,
                # Stop sequences prevent the model from continuing to
                # role-play both sides of the conversation.
                "stop": ["\nUser:", "\nuser:", "\n### Question"],
            },
        }

    # ------------------------------------------------------------------
    # LLMProvider interface
    # ------------------------------------------------------------------

    async def generate(self, prompt: str, context: str = "") -> str:
        """Generate a complete response (non-streaming)."""
        full_prompt = self._build_prompt(prompt, context)
        url = f"{self._base_url}{_OLLAMA_GENERATE_PATH}"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    url,
                    json=self._request_body(full_prompt, stream=False),
                )
                response.raise_for_status()
                data = response.json()
                text: str = data.get("response", "")
        except httpx.ConnectError as exc:
            raise ModelUnavailableError(
                model=self._model,
                reason=f"Cannot connect to Ollama at {self._base_url}: {exc}",
            ) from exc
        except httpx.TimeoutException as exc:
            raise ModelUnavailableError(
                model=self._model,
                reason=f"Ollama request timed out: {exc}",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ModelUnavailableError(
                model=self._model,
                reason=f"Ollama returned HTTP {exc.response.status_code}",
            ) from exc

        log.info(
            "llm_generate_complete",
            model=self._model,
            prompt_chars=len(full_prompt),
            response_chars=len(text),
        )
        return text

    async def stream(self, prompt: str, context: str = "") -> AsyncIterator[str]:  # type: ignore[override]
        """Stream response tokens from Ollama.

        Yields individual text fragments as they are received from the
        Ollama streaming API (newline-delimited JSON).
        """
        full_prompt = self._build_prompt(prompt, context)
        url = f"{self._base_url}{_OLLAMA_GENERATE_PATH}"

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    url,
                    json=self._request_body(full_prompt, stream=True),
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token: str = chunk.get("response", "")
                        if token:
                            yield token
                        if chunk.get("done", False):
                            break
        except httpx.ConnectError as exc:
            raise ModelUnavailableError(
                model=self._model,
                reason=f"Cannot connect to Ollama at {self._base_url}: {exc}",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ModelUnavailableError(
                model=self._model,
                reason=f"Ollama returned HTTP {exc.response.status_code}",
            ) from exc

        log.info("llm_stream_complete", model=self._model)

    @property
    def model_version(self) -> str:
        """Return the Ollama model identifier."""
        return self._model
