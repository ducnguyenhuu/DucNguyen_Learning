"""Message ORM model — a single exchange within a Conversation."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class Message(Base):
    """One message in a conversation (either a user question or an AI answer).

    ``source_references`` stores a JSON array of chunk citations::

        [
            {
                "document_id": "...",
                "file_name": "report.pdf",
                "chunk_ids": ["..._0", "..._1"],
                "relevance_score": 0.87
            }
        ]
    """

    __tablename__ = "messages"
    __table_args__ = (
        # Composite index enables efficient sliding-window queries:
        # SELECT … WHERE conversation_id = ? ORDER BY created_at DESC LIMIT N
        Index("ix_messages_conv_created", "conversation_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="user | assistant",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    source_references: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Array of {document_id, file_name, chunk_ids, relevance_score}",
    )
    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Approximate token count for context window management",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationship back to parent
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        preview = self.content[:40].replace("\n", " ")
        return f"<Message id={self.id!r} role={self.role!r} preview={preview!r}>"
