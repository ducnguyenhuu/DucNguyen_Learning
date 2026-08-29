"""Embedding service — orchestrates text vectorisation via an EmbeddingProvider.

This service acts as the boundary between business logic (ingestion, retrieval)
and the provider abstraction layer.  It:

- Delegates all model I/O to the injected :class:`~app.providers.base.EmbeddingProvider`.
- Tags every returned vector with the provider's ``model_version`` string so
  that ChromaDB metadata can support FR-021 (automatic re-embedding on model
  change).
- Validates inputs early (empty strings) and surface failures as structured
  :class:`~app.core.exceptions.AppError` subclasses rather than raw provider
  exceptions.
- Emits structured log events for observability.

Constitution Principle III: Never import concrete provider classes here.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.providers.base import EmbeddingProvider

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data transfer object
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EmbeddingResult:
    """Carrier for a single embedding result.

    Attributes
    ----------
    vector:
        Unit-normed dense vector of length ``embedding_dimensions``.
    model_version:
        Identifier of the model that produced this vector (e.g.
        ``"nomic-embed-text-v1.5"``).  Stored in ChromaDB metadata for
        FR-021 re-embedding detection.
    text_length:
        Character count of the input text (useful for logging / debugging).
    """

    vector: list[float]
    model_version: str
    text_length: int


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class EmbeddingService:
    """Service layer for text embedding.

    Parameters
    ----------
    provider:
        Any :class:`~app.providers.base.EmbeddingProvider` implementation.
        Injected via :mod:`app.api.deps` — never instantiated here directly.
    """

    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed(self, text: str) -> EmbeddingResult:
        """Embed a single text string and return the vector with metadata.

        Parameters
        ----------
        text:
            Non-empty string to embed.

        Returns
        -------
        EmbeddingResult
            Vector tagged with the active model version.

        Raises
        ------
        ValueError
            If *text* is empty or whitespace-only.
        AppError
            If the underlying provider fails (propagates
            :class:`~app.core.exceptions.ModelUnavailableError`).
        """
        _validate_text(text)
        try:
            log.debug("embedding_text", text_length=len(text), model=self._provider.model_version)
            vector = await self._provider.embed(text)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                message=f"Embedding failed: {exc}",
                code="embedding_error",
            ) from exc

        result = EmbeddingResult(
            vector=vector,
            model_version=self._provider.model_version,
            text_length=len(text),
        )
        log.debug(
            "embedding_complete",
            text_length=len(text),
            dimensions=len(vector),
            model=result.model_version,
        )
        return result

    async def embed_batch(self, texts: list[str]) -> list[EmbeddingResult]:
        """Embed a list of texts in a single provider call.

        Prefer this over looping :meth:`embed` for ingestion batches — most
        providers process batches substantially faster than individual calls.

        Parameters
        ----------
        texts:
            Non-empty list; each element must be a non-empty string.

        Returns
        -------
        list[EmbeddingResult]
            One result per input text, in the same order.

        Raises
        ------
        ValueError
            If *texts* is empty or any element is empty/whitespace-only.
        AppError
            If the underlying provider fails.
        """
        if not texts:
            raise ValueError("texts must not be empty")
        for i, t in enumerate(texts):
            _validate_text(t, context=f"texts[{i}]")

        log.debug(
            "embedding_batch",
            batch_size=len(texts),
            model=self._provider.model_version,
        )
        try:
            vectors = await self._provider.embed_batch(texts)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                message=f"Batch embedding failed: {exc}",
                code="embedding_error",
            ) from exc

        model_ver = self._provider.model_version
        results = [
            EmbeddingResult(
                vector=vec,
                model_version=model_ver,
                text_length=len(text),
            )
            for vec, text in zip(vectors, texts)
        ]
        log.debug(
            "embedding_batch_complete",
            batch_size=len(results),
            dimensions=len(results[0].vector) if results else 0,
            model=model_ver,
        )
        return results

    # ------------------------------------------------------------------
    # Provider pass-through properties
    # ------------------------------------------------------------------

    @property
    def model_version(self) -> str:
        """Active model identifier — delegates to the injected provider."""
        return self._provider.model_version

    @property
    def dimensions(self) -> int:
        """Embedding dimensionality — delegates to the injected provider."""
        return self._provider.dimensions


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate_text(text: str, context: str = "text") -> None:
    """Raise ``ValueError`` if *text* is empty or whitespace-only."""
    if not text or not text.strip():
        raise ValueError(f"{context} must be a non-empty, non-whitespace string")
