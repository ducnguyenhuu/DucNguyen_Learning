"""Document REST routes.

Contract: api-contracts.md §1.4, §1.5, §1.6

GET    /api/v1/documents               — paginated list, optional status filter
GET    /api/v1/documents/{document_id} — document detail with has_summary flag
DELETE /api/v1/documents/{document_id} — remove document + all ChromaDB chunks
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import DbSession, VStore
from app.core.exceptions import DocumentNotFoundError
from app.core.logging import get_logger
from app.models.document import Document
from app.models.document_summary import DocumentSummary

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class DocumentListItem(BaseModel):
    """Single entry in the GET /documents list response (§1.4)."""

    id: str
    file_name: str
    file_type: str
    file_path: str
    chunk_count: int
    status: str
    ingested_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    """Paginated response for GET /documents (§1.4)."""

    documents: list[DocumentListItem]
    total: int
    page: int
    page_size: int


class DocumentDetailResponse(BaseModel):
    """Response for GET /documents/{document_id} (§1.5)."""

    id: str
    file_name: str
    file_type: str
    file_path: str
    file_size_bytes: int
    chunk_count: int
    status: str
    ingested_at: Optional[datetime] = None
    has_summary: bool


class DocumentDeleteResponse(BaseModel):
    """Response for DELETE /documents/{document_id} (§1.6)."""

    message: str
    document_id: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "",
    summary="List ingested documents (§1.4)",
    response_model=DocumentListResponse,
)
async def list_documents(
    db: DbSession,
    status: Optional[str] = Query(
        default=None,
        description="Filter by status: completed | failed | pending | processing",
    ),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=20, ge=1, le=200, description="Results per page"),
) -> DocumentListResponse:
    """Return a paginated list of Documents, optionally filtered by *status*."""
    base_q = select(Document)
    count_q = select(func.count()).select_from(Document)

    if status is not None:
        base_q = base_q.where(Document.status == status)
        count_q = count_q.where(Document.status == status)

    total_result = await db.execute(count_q)
    total: int = total_result.scalar_one()

    offset = (page - 1) * page_size
    rows_result = await db.execute(
        base_q.order_by(Document.ingested_at.desc().nulls_last())
        .offset(offset)
        .limit(page_size)
    )
    docs = rows_result.scalars().all()

    log.info("documents_listed", count=len(docs), total=total, page=page, status=status)

    return DocumentListResponse(
        documents=[
            DocumentListItem(
                id=d.id,
                file_name=d.file_name,
                file_type=d.file_type,
                file_path=d.file_path,
                chunk_count=d.chunk_count,
                status=d.status,
                ingested_at=d.ingested_at,
            )
            for d in docs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{document_id}",
    summary="Get document detail (§1.5)",
    response_model=DocumentDetailResponse,
)
async def get_document(
    document_id: str,
    db: DbSession,
) -> DocumentDetailResponse:
    """Return full metadata for a single document including the ``has_summary`` flag.

    Raises 404 if no document with *document_id* exists.
    """
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc: Document | None = doc_result.scalars().first()

    if doc is None:
        raise DocumentNotFoundError(document_id=document_id)

    # Check whether a summary exists for this document
    summary_result = await db.execute(
        select(func.count())
        .select_from(DocumentSummary)
        .where(DocumentSummary.document_id == document_id)
    )
    has_summary: bool = summary_result.scalar_one() > 0

    log.info("document_fetched", document_id=document_id, has_summary=has_summary)

    return DocumentDetailResponse(
        id=doc.id,
        file_name=doc.file_name,
        file_type=doc.file_type,
        file_path=doc.file_path,
        file_size_bytes=doc.file_size_bytes,
        chunk_count=doc.chunk_count,
        status=doc.status,
        ingested_at=doc.ingested_at,
        has_summary=has_summary,
    )


@router.delete(
    "/{document_id}",
    summary="Delete a document and its chunks (§1.6)",
    response_model=DocumentDeleteResponse,
)
async def delete_document(
    document_id: str,
    db: DbSession,
    vector_store: VStore,
) -> DocumentDeleteResponse:
    """Remove a document record and all its associated ChromaDB chunks.

    Raises 404 if no document with *document_id* exists.
    """
    doc_result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc: Document | None = doc_result.scalars().first()

    if doc is None:
        raise DocumentNotFoundError(document_id=document_id)

    chunk_count = doc.chunk_count

    # Remove vectors from ChromaDB first (idempotent if already absent)
    await vector_store.delete_by_document_id(document_id)

    # Remove the DB row (cascades to DocumentSummary via FK ondelete=CASCADE)
    await db.delete(doc)
    await db.commit()

    log.info(
        "document_deleted",
        document_id=document_id,
        chunks_removed=chunk_count,
    )

    return DocumentDeleteResponse(
        message=f"Document and {chunk_count} chunks removed successfully",
        document_id=document_id,
    )
