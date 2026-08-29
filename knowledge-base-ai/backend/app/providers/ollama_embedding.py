"""Ollama embedding provider.

Calls the Ollama REST API (``POST /api/embed``) to generate embeddings.
This provider requires Ollama to be running and the target model to be pulled.

Example::

    ollama pull nomic-embed-text
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.core.exceptions import ModelUnavailableError
from app.core.logging import get_logger
from app.providers.base import EmbeddingProvider

log = get_logger(__name__)


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Ollama implementation of :class:`EmbeddingProvider`.

    Calls ``POST {ollama_base_url}/api/embed`` synchronously via httpx.
    Runs in the asyncio event loop via an async httpx client.
    """

    def __init__(
        self,
        model_name: str | None = None,
        dimensions: int | None = None,
        base_url: str | None = None,
    ) -> None:
        self._model_name = model_name or settings.embedding_model
        self._dimensions = dimensions or settings.embedding_dimensions
        self._base_url = (base_url or settings.llm_base_url).rstrip("/")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call_embed(self, texts: list[str]) -> list[list[float]]:
        """Call the Ollama /api/embed endpoint for a list of texts."""
        url = f"{self._base_url}/api/embed"
        payload = {"model": self._model_name, "input": texts}
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                body = resp.json()
                vectors: list[list[float]] = body.get("embeddings") or body.get("embedding") or []
                if not vectors:
                    raise ModelUnavailableError(
                        model=self._model_name,
                        reason="Ollama returned no embeddings in response",
                    )
                return vectors
        except httpx.ConnectError as exc:
            raise ModelUnavailableError(
                model=self._model_name,
                reason=f"Cannot connect to Ollama at {self._base_url}: {exc}",
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise ModelUnavailableError(
                model=self._model_name,
                reason=f"Ollama embed request failed: {exc.response.status_code} {exc.response.text}",
            ) from exc

    # ------------------------------------------------------------------
    # EmbeddingProvider interface
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        vectors = await self._call_embed([text])
        return vectors[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts and return raw vectors."""
        if not texts:
            return []

        log.info(
            "ollama_embed_batch",
            model=self._model_name,
            batch_size=len(texts),
        )

        return await self._call_embed(texts)

    @property
    def model_version(self) -> str:
        return self._model_name

    @property
    def dimensions(self) -> int:
        return self._dimensions
