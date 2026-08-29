"""Document summary REST routes.

Contract: api-contracts.md §4.1, §4.2

POST   /api/v1/documents/{document_id}/summary  — generate / regenerate summary
GET    /api/v1/documents/{document_id}/summary  — return cached summary (404 if absent)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DbSession, SummarySvc
from app.core.exceptions import (
    DocumentNotFoundError,
    DocumentNotReadyError,
    ModelUnavailableError,
    SummaryNotFoundError,
)
from app.core.logging import get_logger
from app.models.document import Document
from app.services.summary import SummaryGenerationError

router = APIRouter(prefix="/api/v1/documents", tags=["summary"])

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class SectionReferenceOut(BaseModel):
    """One entry in the section_references array."""

    section: str
    page: Optional[int] = None
    contribution: str


class SummaryResponse(BaseModel):
    """Response for POST and GET /documents/{id}/summary (§4.1, §4.2)."""

    id: str
    document_id: str
    summary_text: str
    section_references: Optional[list[SectionReferenceOut]] = None
    model_version: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/{document_id}/summary",
    summary="Generate or regenerate a document summary (§4.1)",
    response_model=SummaryResponse,
)
async def generate_summary(
    document_id: str,
    db: DbSession,
    summary_svc: SummarySvc,
) -> SummaryResponse:
    """Generate (or regenerate) a summary for *document_id* using the LLM.

    - **404** if the document does not exist.
    - **409** if the document has not been fully ingested yet.
    - **503** if the LLM model is unavailable.
    """
    # Verify document exists
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    doc: Document | None = doc_result.scalars().first()
    if doc is None:
        raise DocumentNotFoundError(document_id=document_id)

    # Verify document is fully ingested
    if doc.status != "completed":
        raise DocumentNotReadyError(document_id=document_id, status=doc.status)

    try:
        record = await summary_svc.get_or_generate(db, doc, regenerate=True)
    except SummaryGenerationError as exc:
        log.warning("summary_generation_failed", document_id=document_id, reason=exc.reason)
        raise ModelUnavailableError(model="LLM", reason=exc.reason) from exc

    return _to_response(record)


@router.get(
    "/{document_id}/summary",
    summary="Get cached document summary (§4.2)",
    response_model=SummaryResponse,
)
async def get_summary(
    document_id: str,
    db: DbSession,
    summary_svc: SummarySvc,
) -> SummaryResponse:
    """Return the previously generated summary for *document_id*.

    - **404** if the document does not exist or has no summary yet.
    """
    # Verify document exists
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    if doc_result.scalars().first() is None:
        raise DocumentNotFoundError(document_id=document_id)

    cached = await summary_svc.get_cached(db, document_id)
    if cached is None:
        raise SummaryNotFoundError(document_id=document_id)

    return _to_response(cached)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(record) -> SummaryResponse:  # type: ignore[no-untyped-def]
    """Map a DocumentSummary ORM record to the API response schema."""
    refs: list[SectionReferenceOut] | None = None
    if record.section_references:
        refs = [
            SectionReferenceOut(
                section=r["section"],
                page=r.get("page"),
                contribution=r.get("contribution", ""),
            )
            for r in record.section_references
        ]
    return SummaryResponse(
        id=record.id,
        document_id=record.document_id,
        summary_text=record.summary_text,
        section_references=refs,
        model_version=record.model_version,
        created_at=record.created_at,
    )
