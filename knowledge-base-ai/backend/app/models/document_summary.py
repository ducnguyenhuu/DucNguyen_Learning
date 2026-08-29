"""DocumentSummary ORM model — cached LLM-generated summaries for documents."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base

if TYPE_CHECKING:
    from app.models.document import Document


class DocumentSummary(Base):
    """Cached summary for a single document.

    At most one summary per document (``document_id`` UNIQUE constraint).
    Re-generating a summary replaces the existing record.
    """

    __tablename__ = "document_summaries"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_document_summaries_document_id"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Source document for this summary",
    )
    summary_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="LLM-generated full summary text",
    )
    section_references: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Array of {section, page, contribution}",
    )
    model_version: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="LLM model identifier used to generate this summary",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    # Relationship back to parent document
    document: Mapped["Document"] = relationship(
        "Document",
        foreign_keys=[document_id],
    )

    def __repr__(self) -> str:
        preview = self.summary_text[:60].replace("\n", " ")
        return (
            f"<DocumentSummary id={self.id!r} document_id={self.document_id!r} "
            f"preview={preview!r}>"
        )
