"""Conversation REST routes.

Contracts: api-contracts.md §2.1–§2.5

POST   /api/v1/conversations               — create a new empty conversation (§2.1)
GET    /api/v1/conversations               — paginated list (§2.2)
GET    /api/v1/conversations/{id}          — full message history (§2.3)
DELETE /api/v1/conversations/{id}          — single cascade delete (§2.4)
DELETE /api/v1/conversations?confirm=true  — bulk clear (§2.5, FR-024)
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select

from app.api.deps import DbSession
from app.core.logging import get_logger
from app.models.conversation import Conversation
from app.models.message import Message

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateConversationRequest(BaseModel):
    """Optional request body for POST /conversations (§2.1)."""

    title: Optional[str] = None


class ConversationResponse(BaseModel):
    """Response for POST /conversations (§2.1)."""

    id: str
    title: Optional[str]
    preview: Optional[str]
    message_count: int
    created_at: datetime


class ConversationListItem(BaseModel):
    """One item in the paginated conversation list (§2.2)."""

    id: str
    title: Optional[str]
    preview: Optional[str]
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """Paginated list response for GET /conversations (§2.2)."""

    conversations: list[ConversationListItem]
    total: int
    page: int
    page_size: int


class MessageResponse(BaseModel):
    """One message in a conversation detail response (§2.3)."""

    id: str
    role: str
    content: str
    source_references: Optional[list[dict[str, Any]]]
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    """Full conversation with message history (§2.3)."""

    id: str
    title: Optional[str]
    messages: list[MessageResponse]
    created_at: datetime
    updated_at: datetime


class DeleteConversationResponse(BaseModel):
    """Response for DELETE /conversations/{id} (§2.4)."""

    message: str
    conversation_id: str


class ClearConversationsResponse(BaseModel):
    """Response for DELETE /conversations?confirm=true (§2.5)."""

    message: str
    deleted_count: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=201,
    summary="Create a new conversation (§2.1)",
    response_model=ConversationResponse,
)
async def create_conversation(
    db: DbSession,
    body: Optional[CreateConversationRequest] = Body(default=None),
) -> ConversationResponse:
    """Create a new empty conversation.

    An optional ``title`` can be provided; if omitted the conversation title
    will be auto-set to the first 100 characters of the first user message
    when it is sent.
    """
    title: Optional[str] = body.title if body else None
    now = datetime.now(UTC)
    conv = Conversation(
        id=str(uuid.uuid4()),
        title=title,
        preview=None,
        message_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)

    log.info("conversation_created", conversation_id=conv.id, title=conv.title)

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        preview=conv.preview,
        message_count=conv.message_count,
        created_at=conv.created_at,
    )


@router.get(
    "",
    status_code=200,
    summary="List conversations — paginated (§2.2)",
    response_model=ConversationListResponse,
)
async def list_conversations(
    db: DbSession,
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(default=20, ge=1, le=200, description="Results per page"),
) -> ConversationListResponse:
    """Return all conversations sorted by *updated_at* DESC, newest first."""
    total_result = await db.execute(
        select(func.count()).select_from(Conversation)
    )
    total: int = total_result.scalar_one()

    offset = (page - 1) * page_size
    rows_result = await db.execute(
        select(Conversation)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    convs = rows_result.scalars().all()

    log.info("conversations_listed", total=total, page=page, page_size=page_size)

    return ConversationListResponse(
        conversations=[
            ConversationListItem(
                id=c.id,
                title=c.title,
                preview=c.preview,
                message_count=c.message_count,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in convs
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{conversation_id}",
    status_code=200,
    summary="Get conversation with full message history (§2.3)",
    response_model=ConversationDetailResponse,
)
async def get_conversation(
    conversation_id: str,
    db: DbSession,
) -> ConversationDetailResponse:
    """Return a conversation with its complete message history.

    Messages are loaded via the ``selectin`` relationship defined on the ORM
    model and returned ordered by *created_at* ASC.

    Raises ``404`` if the conversation does not exist.
    """
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv: Conversation | None = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id!r} not found",
        )

    # Explicitly load messages sorted by created_at ASC
    msgs_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages: list[Message] = list(msgs_result.scalars().all())

    log.info(
        "conversation_fetched",
        conversation_id=conversation_id,
        message_count=len(messages),
    )

    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        messages=[
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                source_references=m.source_references,
                created_at=m.created_at,
            )
            for m in messages
        ],
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.delete(
    "/{conversation_id}",
    status_code=200,
    summary="Delete a single conversation and its messages (§2.4)",
    response_model=DeleteConversationResponse,
)
async def delete_conversation(
    conversation_id: str,
    db: DbSession,
) -> DeleteConversationResponse:
    """Delete a conversation and all its messages (cascade handled by ORM).

    Raises ``404`` if the conversation does not exist.
    """
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv: Conversation | None = result.scalar_one_or_none()
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id!r} not found",
        )

    await db.delete(conv)
    await db.commit()

    log.info("conversation_deleted", conversation_id=conversation_id)

    return DeleteConversationResponse(
        message="Conversation deleted successfully",
        conversation_id=conversation_id,
    )


@router.delete(
    "",
    status_code=200,
    summary="Delete ALL conversations (bulk clear, §2.5, FR-024)",
    response_model=ClearConversationsResponse,
)
async def clear_conversations(
    db: DbSession,
    confirm: Optional[bool] = Query(
        default=None,
        description="Must be true to execute the bulk delete (FR-024)",
    ),
) -> ClearConversationsResponse:
    """Delete every conversation and all messages.

    The ``confirm=true`` query parameter is **required** to prevent accidental
    deletion (FR-024).  Returns ``400`` if it is missing or ``false``.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="confirm=true is required to bulk-delete all conversations",
        )

    count_result = await db.execute(
        select(func.count()).select_from(Conversation)
    )
    total: int = count_result.scalar_one()

    await db.execute(sa_delete(Conversation))
    await db.commit()

    log.info("conversations_cleared", deleted_count=total)

    return ClearConversationsResponse(
        message="All conversations deleted successfully",
        deleted_count=total,
    )
