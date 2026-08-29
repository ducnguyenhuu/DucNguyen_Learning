"""IngestionJob ORM model — tracks batch ingestion runs."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

IngestionJobStatus = Literal["running", "completed", "failed"]
TriggerReason = Literal["user", "reembed"]


class IngestionJob(Base):
    """Records a single ingestion run for progress reporting and audit.

    State transitions::

        running → completed
               → failed

    ``trigger_reason`` distinguishes between user-initiated (``"user"``) and
    automatic re-embedding triggered by a model-version mismatch (``"reembed"``
    per FR-021).
    """

    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        Index("ix_ingestion_jobs_started_at", "started_at"),
        Index("ix_ingestion_jobs_status", "status"),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    source_folder: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        comment="Absolute path to the knowledge folder being ingested",
    )
    trigger_reason: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="user",
        comment="user | reembed — why this job was created",
    )
    total_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total files discovered in the source folder",
    )
    processed_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Files successfully processed so far",
    )
    new_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    modified_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    deleted_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    skipped_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Unsupported format or files that errored during parse",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="running",
        comment="running | completed | failed",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Top-level error detail when status = failed",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of completion (success or failure)",
    )

    @property
    def progress_pct(self) -> float:
        """0–100 progress percentage."""
        if self.total_files == 0:
            return 0.0
        return round(self.processed_files / self.total_files * 100, 1)

    def __repr__(self) -> str:
        return (
            f"<IngestionJob id={self.id!r} status={self.status!r} "
            f"progress={self.progress_pct}%>"
        )
