"""Retrieval service — semantic search over the ChromaDB vector store.

Given a natural-language query this service:

1. Embeds the query text via the injected :class:`~app.providers.base.EmbeddingProvider`.
2. Queries ChromaDB through :class:`~app.db.vector_store.VectorStore` with
   configurable ``top_k`` and ``similarity_threshold`` (FR-008).
3. Filters out any results below the threshold (already done inside
   ``VectorStore.query``, enforced here for explicit visibility).
4. Returns an ordered list of :class:`RetrievalResult` objects — one per
   chunk — sorted by descending relevance score.

The service also exposes :class:`SourceReference`, a compact DTO that
captures only the fields required by the API contract and stored in
``Message.source_references`` JSON:

    ``{document_id, file_name, page_number, relevance_score}``

Constitution Principle III: Only interface types from ``providers/base.py``
are imported here — no concrete providers.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.db.vector_store import VectorStore
from app.providers.base import EmbeddingProvider

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Compact source citation stored in Message.source_references JSON.

    Matches the API contract schema for source references:
        ``{document_id, file_name, page_number, relevance_score}``
    """

    document_id: str
    file_name: str
    page_number: int | None
    relevance_score: float

    def to_dict(self) -> dict[str, object]:
        """Serialise to a plain dict for JSON storage / API responses."""
        return {
            "document_id": self.document_id,
            "file_name": self.file_name,
            "page_number": self.page_number,
            "relevance_score": round(self.relevance_score, 4),
        }


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """Full retrieval result for a single matching chunk.

    Contains everything the chat service needs to:
    - Build an LLM prompt (``text``, ``file_name``, ``page_number``).
    - Construct ``SourceReference`` objects for the API response.
    - Log / debug retrieval quality (``relevance_score``, ``chunk_index``).
    """

    chunk_id: str
    document_id: str
    file_name: str
    file_path: str
    text: str
    chunk_index: int
    total_chunks: int
    page_number: int | None
    relevance_score: float
    model_version: str = field(default="")

    def to_source_reference(self) -> SourceReference:
        """Convert to the compact citation DTO used in API responses."""
        return SourceReference(
            document_id=self.document_id,
            file_name=self.file_name,
            page_number=self.page_number,
            relevance_score=self.relevance_score,
        )


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RetrievalService:
    """Semantic retrieval over the ChromaDB knowledge base.

    Parameters
    ----------
    embedding_provider:
        Provider used to embed the incoming query text.
    vector_store:
        ChromaDB wrapper used to execute the nearest-neighbour search.
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> list[RetrievalResult]:
        """Embed *query* and return the most relevant document chunks.

        Parameters
        ----------
        query:
            Natural-language question from the user. Must be non-empty.
        top_k:
            Maximum number of results to return.  Defaults to
            ``settings.retrieval_top_k`` (configured via FR-008).
        similarity_threshold:
            Minimum cosine similarity score (0–1).  Chunks below this
            threshold are excluded.  Defaults to
            ``settings.retrieval_similarity_threshold`` (FR-008).

        Returns
        -------
        list[RetrievalResult]
            Chunks sorted by descending ``relevance_score``.  Empty list
            when no chunks exceed the threshold (chat service treats this
            as "no relevant information" — FR-008).

        Raises
        ------
        AppError
            If the query is empty or the embedding provider fails.
        """
        query = query.strip()
        if not query:
            raise AppError("Query must be a non-empty string.")

        k = top_k if top_k is not None else settings.retrieval_top_k
        threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else settings.retrieval_similarity_threshold
        )

        log.info(
            "retrieval_started",
            query_length=len(query),
            top_k=k,
            similarity_threshold=threshold,
        )

        # 1. Embed the query
        try:
            query_vector = await self._embedding_provider.embed(query)
        except Exception as exc:
            log.error("retrieval_embed_failed", error=str(exc))
            raise AppError(f"Failed to embed query: {exc}") from exc

        # 2. Query ChromaDB — VectorStore already applies the threshold filter
        chunk_results = await self._vector_store.query(
            query_embedding=query_vector,
            top_k=k,
            similarity_threshold=threshold,
        )

        # 3. Map ChunkResult → RetrievalResult (explicit re-filter for safety)
        results: list[RetrievalResult] = []
        for cr in chunk_results:
            score = cr.relevance_score  # 1.0 - cosine_distance
            if score < threshold:
                continue
            results.append(
                RetrievalResult(
                    chunk_id=cr.chunk_id,
                    document_id=cr.document_id,
                    file_name=cr.file_name,
                    file_path=cr.file_path,
                    text=cr.text,
                    chunk_index=cr.chunk_index,
                    total_chunks=cr.total_chunks,
                    page_number=cr.page_number,
                    relevance_score=score,
                    model_version=cr.model_version,
                )
            )

        # Sort highest relevance first (VectorStore usually returns sorted, but
        # enforce explicitly for deterministic ordering)
        results.sort(key=lambda r: r.relevance_score, reverse=True)

        log.info(
            "retrieval_done",
            query_length=len(query),
            top_k=k,
            threshold=threshold,
            results_count=len(results),
        )
        return results
