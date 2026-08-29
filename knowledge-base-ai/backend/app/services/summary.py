"""On-demand document summarization service (FR-017, FR-018).

Algorithm
---------
1. Fetch all ChromaDB chunks for the document ordered by ``chunk_index``.
2. Batch the chunks (``CHUNK_BATCH_SIZE`` per batch) and send each batch to
   the LLM to produce a partial summary.
3. If more than one batch was processed, ask the LLM to combine all partial
   summaries into one coherent summary (iterative summarization — FR-017).
4. Extract section references from chunk metadata: unique page numbers mapped
   to the start of their first chunk (FR-018).
5. Upsert the ``DocumentSummary`` ORM record and return it.

Caching
-------
``get_or_generate()`` short-circuits if a summary already exists and
``regenerate=False`` (the default).  The POST route always passes
``regenerate=True`` on explicit user request.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.db.vector_store import ChunkResult, VectorStore
from app.models.document import Document
from app.models.document_summary import DocumentSummary
from app.providers.base import LLMProvider

log = get_logger(__name__)

# Number of chunks sent to the LLM in each summarization batch.
# Smaller = shorter prompts (safer for small context windows).
_CHUNK_BATCH_SIZE = 6

# Maximum section references to include in the response.
_MAX_SECTION_REFS = 10

# Character limit for the contribution snippet in each section reference.
_SNIPPET_LEN = 140


class SummaryService:
    """Orchestrates iterative LLM summarization and caches results in SQLite."""

    def __init__(
        self,
        vector_store: VectorStore,
        llm_provider: LLMProvider,
        llm_model: str | None = None,
    ) -> None:
        self._vector_store = vector_store
        self._llm_provider = llm_provider
        self._llm_model = llm_model or settings.llm_model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_or_generate(
        self,
        db: AsyncSession,
        document: Document,
        *,
        regenerate: bool = False,
    ) -> DocumentSummary:
        """Return the cached summary or generate a new one.

        Parameters
        ----------
        db:
            SQLAlchemy async session (will be committed by this method).
        document:
            The ``Document`` ORM instance to summarize.
        regenerate:
            If ``True``, bypass the cache and always call the LLM.
        """
        if not regenerate:
            cached = await self.get_cached(db, document.id)
            if cached is not None:
                log.info("summary_cache_hit", document_id=document.id)
                return cached

        log.info("summary_generation_start", document_id=document.id, regenerate=regenerate)
        return await self._generate(db, document)

    async def get_cached(
        self,
        db: AsyncSession,
        document_id: str,
    ) -> DocumentSummary | None:
        """Return the cached ``DocumentSummary`` for *document_id*, or ``None``."""
        result = await db.execute(
            select(DocumentSummary).where(DocumentSummary.document_id == document_id)
        )
        return result.scalars().first()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _generate(self, db: AsyncSession, document: Document) -> DocumentSummary:
        """Generate a fresh summary via iterative LLM calls."""
        # Step 1 — fetch chunks
        chunks = await self._vector_store.get_chunks_by_document_id(document.id)
        if not chunks:
            raise SummaryGenerationError(
                document_id=document.id,
                reason="No chunks found in vector store — has the document been ingested?",
            )

        # Step 2 — batch-summarize
        partial_summaries: list[str] = []
        for batch_start in range(0, len(chunks), _CHUNK_BATCH_SIZE):
            batch: list[ChunkResult] = chunks[batch_start : batch_start + _CHUNK_BATCH_SIZE]
            context = "\n\n---\n\n".join(c.text for c in batch)
            partial = await self._llm_provider.generate(
                prompt=(
                    "Summarize the following document sections concisely. "
                    "Capture the main ideas, key facts, and important details."
                ),
                context=context,
            )
            partial_summaries.append(partial.strip())
            log.debug(
                "summary_batch_done",
                document_id=document.id,
                batch=batch_start // _CHUNK_BATCH_SIZE + 1,
                chunks_in_batch=len(batch),
            )

        # Step 3 — combine (FR-017 iterative summarization)
        if len(partial_summaries) > 1:
            combined_context = "\n\n---\n\n".join(partial_summaries)
            final_text = await self._llm_provider.generate(
                prompt=(
                    "Combine the following partial summaries into a single, "
                    "coherent summary. Preserve all key information."
                ),
                context=combined_context,
            )
            final_text = final_text.strip()
        else:
            final_text = partial_summaries[0]

        # Step 4 — build section references (FR-018)
        section_refs = self._build_section_refs(chunks)

        # Step 5 — upsert DocumentSummary
        existing_result = await db.execute(
            select(DocumentSummary).where(DocumentSummary.document_id == document.id)
        )
        record: DocumentSummary | None = existing_result.scalars().first()

        now = datetime.now(UTC)
        if record is not None:
            record.summary_text = final_text
            record.section_references = section_refs
            record.model_version = self._llm_model
            record.created_at = now
            log.info("summary_updated", document_id=document.id)
        else:
            record = DocumentSummary(
                document_id=document.id,
                summary_text=final_text,
                section_references=section_refs,
                model_version=self._llm_model,
                created_at=now,
            )
            db.add(record)
            log.info("summary_created", document_id=document.id)

        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    def _build_section_refs(chunks: list[ChunkResult]) -> list[dict[str, Any]] | None:
        """Build section references from chunk page metadata (FR-018).

        Each unique page number becomes one reference entry.  We capture the
        first sentence-or-so of the first chunk on that page as a
        "contribution" snippet.
        """
        seen_pages: set[int] = set()
        refs: list[dict[str, Any]] = []

        for chunk in chunks:
            if chunk.page_number is None:
                continue
            if chunk.page_number in seen_pages:
                continue

            seen_pages.add(chunk.page_number)
            snippet = chunk.text[:_SNIPPET_LEN].strip().replace("\n", " ")
            if len(chunk.text) > _SNIPPET_LEN:
                # Trim at last word boundary
                last_space = snippet.rfind(" ")
                if last_space > 0:
                    snippet = snippet[:last_space] + "…"

            refs.append(
                {
                    "section": f"Page {chunk.page_number}",
                    "page": chunk.page_number,
                    "contribution": snippet or "(no text)",
                }
            )

            if len(refs) >= _MAX_SECTION_REFS:
                break

        return refs if refs else None


class SummaryGenerationError(Exception):
    """Raised when summary generation fails (no chunks, LLM error, etc.)."""

    def __init__(self, document_id: str, reason: str) -> None:
        super().__init__(f"Summary generation failed for {document_id}: {reason}")
        self.document_id = document_id
        self.reason = reason
