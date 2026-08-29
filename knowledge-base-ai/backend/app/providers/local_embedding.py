"""sentence-transformers embedding provider.

Loads the ``nomic-embed-text-v1.5`` model on first use and runs inference in
a thread-pool executor so it does not block the asyncio event loop.

The model files are downloaded to ``~/.cache/huggingface/hub/`` on first run
(~275 MB).  Subsequent starts reuse the cached files.
"""
from __future__ import annotations

import asyncio
from typing import cast

from app.config import settings
from app.core.exceptions import ModelUnavailableError
from app.core.logging import get_logger
from app.providers.base import EmbeddingProvider

log = get_logger(__name__)


class LocalEmbeddingProvider(EmbeddingProvider):
    """sentence-transformers implementation of :class:`EmbeddingProvider`.

    Uses the ``nomic-embed-text-v1.5`` model (768-dimensional vectors,
    cosine similarity).  The ``trust_remote_code=True`` flag is required by
    the nomic model architecture.
    """

    def __init__(
        self,
        model_name: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        self._model_name = model_name or settings.embedding_model
        self._dimensions = dimensions or settings.embedding_dimensions
        self._model: object | None = None  # lazy initialisation

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_model(self) -> object:
        """Load the sentence-transformers model synchronously (called in thread pool)."""
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
        except ImportError as exc:
            raise ModelUnavailableError(
                model=self._model_name,
                reason="sentence-transformers is not installed",
            ) from exc

        try:
            log.info("loading_embedding_model", model=self._model_name)
            self._model = SentenceTransformer(
                self._model_name,
                trust_remote_code=True,
            )
            log.info("embedding_model_loaded", model=self._model_name)
        except Exception as exc:
            raise ModelUnavailableError(
                model=self._model_name,
                reason=str(exc),
            ) from exc
        return self._model

    # ------------------------------------------------------------------
    # EmbeddingProvider interface
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string.

        Runs model inference in a thread-pool executor to avoid blocking the
        asyncio event loop during the potentially multi-second forward pass.
        """

        def _run() -> list[float]:
            model = self._load_model()
            embedding = model.encode(  # type: ignore[attr-defined]
                text,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return cast(list[float], embedding.tolist())

        return await asyncio.get_event_loop().run_in_executor(None, _run)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts in a single forward pass.

        Significantly faster than calling ``embed()`` in a loop for
        large document ingestion batches.
        """

        def _run_batch() -> list[list[float]]:
            model = self._load_model()
            embeddings = model.encode(  # type: ignore[attr-defined]
                texts,
                normalize_embeddings=True,
                batch_size=32,
                show_progress_bar=False,
            )
            return [e.tolist() for e in embeddings]

        return await asyncio.get_event_loop().run_in_executor(None, _run_batch)

    @property
    def model_version(self) -> str:
        """Return the model identifier for vector metadata tagging."""
        return self._model_name

    @property
    def dimensions(self) -> int:
        """Return the number of output dimensions (768 for nomic-embed-text-v1.5)."""
        return self._dimensions
