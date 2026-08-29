"""Document ORM model — tracks source files in the knowledge folder."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

DocumentStatus = Literal["pending", "processing", "completed", "failed"]
FileType = Literal["pdf", "docx", "md"]


class Document(Base):
    """Represents a source document in the knowledge folder.

    State transitions::

        pending → processing → completed
                             → failed
    """

    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_file_hash", "file_hash"),
        Index("ix_documents_status", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    file_path: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        unique=True,
        index=True,
        comment="Absolute path to the source file",
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Filename for display",
    )
    file_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="pdf | docx | md",
    )
    file_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hex digest for change detection",
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of chunks stored in ChromaDB",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="pending | processing | completed | failed",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error detail when status = failed",
    )
    ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When ingestion completed",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id!r} file_name={self.file_name!r} status={self.status!r}>"
