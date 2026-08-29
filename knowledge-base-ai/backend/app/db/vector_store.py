"""ChromaDB persistent client and collection manager.

Wraps the ChromaDB API to provide add/delete/query operations
for document chunks used during ingestion and retrieval.

Usage
-----
    from app.db.vector_store import VectorStore

    store = VectorStore()           # uses settings from config
    await store.add_chunks(chunks)
    results = await store.query("What is X?", top_k=5)
    await store.delete_by_document_id("some-uuid")
"""
from __future__ import annotations

import asyncio
from typing import Any

import chromadb
from chromadb import Collection
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class ChunkResult:
    """Lightweight container for a single retrieved chunk."""

    __slots__ = (
        "chunk_id",
        "document_id",
        "file_name",
        "file_path",
        "text",
        "chunk_index",
        "total_chunks",
        "page_number",
        "model_version",
        "distance",
    )

    def __init__(
        self,
        chunk_id: str,
        document_id: str,
        file_name: str,
        file_path: str,
        text: str,
        chunk_index: int,
        total_chunks: int,
        page_number: int | None,
        model_version: str,
        distance: float,
    ) -> None:
        self.chunk_id = chunk_id
        self.document_id = document_id
        self.file_name = file_name
        self.file_path = file_path
        self.text = text
        self.chunk_index = chunk_index
        self.total_chunks = total_chunks
        self.page_number = page_number
        self.model_version = model_version
        self.distance = distance

    @property
    def relevance_score(self) -> float:
        """Convert cosine distance → similarity score (1 = identical)."""
        return 1.0 - self.distance


class VectorStore:
    """Thin async-friendly wrapper around a ChromaDB persistent collection."""

    def __init__(
        self,
        persist_dir: str | None = None,
        collection_name: str | None = None,
    ) -> None:
        self._persist_dir = persist_dir or settings.chroma_persist_dir
        self._collection_name = collection_name or settings.chroma_collection_name
        self._client: chromadb.PersistentClient | None = None
        self._collection: Collection | None = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> Collection:
        """Lazily initialise the ChromaDB client and collection."""
        if self._collection is not None:
            return self._collection

        self._client = chromadb.PersistentClient(
            path=self._persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        log.info(
            "vector_store_connected",
            collection=self._collection_name,
            persist_dir=self._persist_dir,
            doc_count=self._collection.count(),
        )
        return self._collection

    # ------------------------------------------------------------------
    # Public API (all operations run in a thread pool to stay async-safe)
    # ------------------------------------------------------------------

    async def add_chunks(
        self,
        chunk_ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Add (upsert) a batch of chunk vectors to the collection.

        Parameters
        ----------
        chunk_ids:
            Unique IDs in format ``{document_id}_{chunk_index}``.
        embeddings:
            Corresponding 768-dimensional float vectors.
        texts:
            Raw chunk text for each vector.
        metadatas:
            Dicts containing ``document_id``, ``file_name``, ``file_path``,
            ``chunk_index``, ``total_chunks``, ``page_number``,
            ``model_version``, ``ingested_at``.
        """

        def _add() -> None:
            col = self._ensure_connected()
            col.upsert(
                ids=chunk_ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )

        await asyncio.get_event_loop().run_in_executor(None, _add)
        log.info("chunks_added", count=len(chunk_ids))

    async def delete_by_document_id(self, document_id: str) -> None:
        """Delete all chunks associated with *document_id*."""

        def _delete() -> None:
            col = self._ensure_connected()
            col.delete(where={"document_id": document_id})

        await asyncio.get_event_loop().run_in_executor(None, _delete)
        log.info("chunks_deleted", document_id=document_id)

    async def query(
        self,
        query_embedding: list[float],
        top_k: int | None = None,
        similarity_threshold: float | None = None,
    ) -> list[ChunkResult]:
        """Query the collection and return the top-K most similar chunks.

        Parameters
        ----------
        query_embedding:
            768-dimensional query vector (already embedded by the caller).
        top_k:
            Maximum number of results; defaults to ``settings.retrieval_top_k``.
        similarity_threshold:
            Minimum similarity score (1 - cosine_distance); defaults to
            ``settings.retrieval_similarity_threshold``.

        Returns
        -------
        list[ChunkResult]
            Results sorted by relevance (highest first), filtered to those
            meeting the similarity threshold.
        """
        k = top_k or settings.retrieval_top_k
        threshold = (
            similarity_threshold
            if similarity_threshold is not None
            else settings.retrieval_similarity_threshold
        )

        def _query() -> chromadb.QueryResult:
            col = self._ensure_connected()
            return col.query(
                query_embeddings=[query_embedding],
                n_results=k,
                include=["documents", "metadatas", "distances"],
            )

        raw: chromadb.QueryResult = await asyncio.get_event_loop().run_in_executor(
            None, _query
        )

        results: list[ChunkResult] = []
        if not raw["ids"] or not raw["ids"][0]:
            return results

        for i, chunk_id in enumerate(raw["ids"][0]):
            distance = float(raw["distances"][0][i])
            similarity = 1.0 - distance
            if similarity < threshold:
                continue
            meta: dict[str, Any] = raw["metadatas"][0][i]
            text: str = raw["documents"][0][i]
            results.append(
                ChunkResult(
                    chunk_id=chunk_id,
                    document_id=str(meta.get("document_id", "")),
                    file_name=str(meta.get("file_name", "")),
                    file_path=str(meta.get("file_path", "")),
                    text=text,
                    chunk_index=int(meta.get("chunk_index", 0)),
                    total_chunks=int(meta.get("total_chunks", 1)),
                    page_number=int(meta["page_number"]) if meta.get("page_number") else None,
                    model_version=str(meta.get("model_version", "")),
                    distance=distance,
                )
            )

        log.debug("vector_query_done", top_k=k, results_returned=len(results))
        return results

    async def get_any_model_version(self) -> str | None:
        """Return the ``model_version`` metadata from any stored vector.

        Used at startup by ``model_manager.py`` to detect stale embeddings
        (FR-021).  Returns ``None`` if the collection is empty.
        """

        def _peek() -> str | None:
            col = self._ensure_connected()
            if col.count() == 0:
                return None
            peeked = col.peek(limit=1)
            metas = peeked.get("metadatas")
            if metas:
                # peek() returns metadatas as list[dict], not list[list[dict]]
                first = metas[0]
                if isinstance(first, dict):
                    return str(first.get("model_version", ""))
                if isinstance(first, list) and first:
                    return str(first[0].get("model_version", ""))
            return None

        return await asyncio.get_event_loop().run_in_executor(None, _peek)

    async def get_chunks_by_document_id(self, document_id: str) -> list[ChunkResult]:
        """Return all chunks for *document_id* ordered by chunk_index.

        Uses ChromaDB ``get()`` (filter by metadata) rather than ``query()``
        (semantic search) to retrieve every stored chunk for a document.
        """

        def _get() -> list[ChunkResult]:
            col = self._ensure_connected()
            raw = col.get(
                where={"document_id": document_id},
                include=["documents", "metadatas"],
            )
            ids: list[str] = raw.get("ids") or []
            docs: list[str] = raw.get("documents") or []
            metas: list[dict[str, Any]] = raw.get("metadatas") or []

            results: list[ChunkResult] = []
            for i, chunk_id in enumerate(ids):
                meta: dict[str, Any] = metas[i] if i < len(metas) else {}
                text: str = docs[i] if i < len(docs) else ""
                results.append(
                    ChunkResult(
                        chunk_id=chunk_id,
                        document_id=str(meta.get("document_id", "")),
                        file_name=str(meta.get("file_name", "")),
                        file_path=str(meta.get("file_path", "")),
                        text=text,
                        chunk_index=int(meta.get("chunk_index", 0)),
                        total_chunks=int(meta.get("total_chunks", 1)),
                        page_number=int(meta["page_number"]) if meta.get("page_number") else None,
                        model_version=str(meta.get("model_version", "")),
                        distance=0.0,
                    )
                )
            results.sort(key=lambda c: c.chunk_index)
            return results

        return await asyncio.get_event_loop().run_in_executor(None, _get)

    async def count(self) -> int:
        """Return the total number of vectors in the collection."""

        def _count() -> int:
            return int(self._ensure_connected().count())

        return await asyncio.get_event_loop().run_in_executor(None, _count)
