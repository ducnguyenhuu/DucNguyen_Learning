"""Ingestion service — orchestrates the full document ingestion pipeline.

Pipeline
--------
1. Pre-flight: disk space check (configurable threshold, Edge Case §disk-space)
2. Path validation: source_folder must exist, be a directory, and resolve
   symlinks (FR-023).
3. Conflict check: single active job enforcement (FR-022).
4. Create IngestionJob record (status = "running").
5. Scan folder recursively; skip unsupported extensions with WARNING log
   (FR-016).
6. Compute SHA-256 hashes; classify files as new / modified / unchanged /
   deleted (FR-005).
7. Remove deleted documents from SQL DB and ChromaDB.
8. For each new/modified/resume file: pending → processing → completed/failed.
   Parse → chunk → embed (batch) → upsert vectors in ChromaDB.
9. Resume-safe: on restart, documents with status processing/pending are
   re-processed from scratch (FR-005).
10. Emit structured progress events via an optional async-or-sync callback.

Constitution Principle III: No concrete provider imports here.
Constitution Principle IV: Every significant operation carries structured log
fields including ``job_id`` and ``file_name``.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, IngestionConflictError, PathValidationError
from app.core.logging import get_logger
from app.models.document import Document
from app.models.ingestion_job import IngestionJob, TriggerReason
from app.parsers import (
    Chunker,
    DocxParser,
    ExcelParser,
    MarkdownParser,
    ParserError,
    PdfParser,
    TextChunk,
)
from app.services.embedding import EmbeddingService

if TYPE_CHECKING:
    from app.db.vector_store import VectorStore

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx", ".md", ".xlsx"})

# Sentinel value stored in ChromaDB metadata when page number is unknown.
_NO_PAGE_NUMBER: int = -1

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[dict[str, Any]], "Awaitable[None] | None"]

_ChangeReason = Literal["new", "modified", "resume"]


class _ScannedFile:
    """Internal DTO for a single file found during folder scan."""

    __slots__ = ("path", "extension", "file_hash", "file_size_bytes", "file_name")

    def __init__(
        self,
        path: str,
        extension: str,
        file_hash: str,
        file_size_bytes: int,
        file_name: str,
    ) -> None:
        self.path = path
        self.extension = extension
        self.file_hash = file_hash
        self.file_size_bytes = file_size_bytes
        self.file_name = file_name


# ---------------------------------------------------------------------------
# Parser registry (singletons, stateless)
# ---------------------------------------------------------------------------

_PARSERS: dict[str, PdfParser | DocxParser | MarkdownParser | ExcelParser] = {
    ".pdf": PdfParser(),
    ".docx": DocxParser(),
    ".md": MarkdownParser(),
    ".xlsx": ExcelParser(),
}

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class IngestionService:
    """Business logic for the document ingestion pipeline.

    Parameters
    ----------
    db:
        Async SQLAlchemy session.  Must be flushed/committed by the caller
        after :meth:`start_ingestion` to persist the job record.
    vector_store:
        ChromaDB wrapper — handles upsert and delete of chunk vectors.
    embedding_service:
        Delegates to the configured ``EmbeddingProvider``; never imported
        directly (Constitution Principle III).
    chunker:
        Text chunker configured with chunk_size / chunk_overlap from Settings.
    min_disk_space_mb:
        Minimum free disk space (MB) required before ingestion begins.
        Defaults to ``settings.min_disk_space_mb`` (500 MB).
    """

    def __init__(
        self,
        db: AsyncSession,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        chunker: Chunker,
        min_disk_space_mb: int | None = None,
    ) -> None:
        self._db = db
        self._vector_store = vector_store
        self._embedding_service = embedding_service
        self._chunker = chunker

        if min_disk_space_mb is not None:
            self._min_disk_space_mb = min_disk_space_mb
        else:
            from app.config import settings  # lazy import avoids circular deps

            self._min_disk_space_mb = settings.min_disk_space_mb

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_ingestion(
        self,
        source_folder: str,
        trigger_reason: TriggerReason = "user",
    ) -> IngestionJob:
        """Validate inputs and create the IngestionJob record.

        Performs all pre-flight checks synchronously so callers can return
        HTTP 400 / 409 immediately.  The actual file processing is in
        :meth:`run_pipeline`, which is intended to run as a background task.

        Parameters
        ----------
        source_folder:
            Absolute or relative path to the folder containing documents.
        trigger_reason:
            ``"user"`` for manual runs; ``"reembed"`` for automatic
            re-embedding triggered by a model-version mismatch (FR-021).

        Returns
        -------
        IngestionJob
            Newly created job record with ``status = "running"``.

        Raises
        ------
        AppError (400)
            If free disk space is below ``min_disk_space_mb``.
        PathValidationError (422)
            If *source_folder* does not exist, is not a directory, or is not
            readable (FR-023).
        IngestionConflictError (409)
            If another job with ``status = "running"`` exists (FR-022).
        """
        # 1. Disk space pre-flight
        _check_disk_space(source_folder, self._min_disk_space_mb)

        # 2. Path validation (FR-023)
        resolved_path = _validate_folder_path(source_folder)

        # 3. Single-job enforcement (FR-022)
        await self._check_no_running_job()

        # 4. Create IngestionJob — set counter columns explicitly so Python
        #    attributes are non-None before a DB flush resolves the defaults.
        job = IngestionJob(
            id=str(uuid.uuid4()),
            source_folder=resolved_path,
            trigger_reason=trigger_reason,
            status="running",
            total_files=0,
            processed_files=0,
            new_files=0,
            modified_files=0,
            deleted_files=0,
            skipped_files=0,
            started_at=datetime.now(UTC),
        )
        self._db.add(job)
        await self._db.flush()

        log.info(
            "ingestion_job_created",
            job_id=job.id,
            source_folder=resolved_path,
            trigger_reason=trigger_reason,
        )
        return job

    async def run_pipeline(
        self,
        job: IngestionJob,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Execute the full ingestion pipeline for an existing IngestionJob.

        Designed to run as an ``asyncio`` background task / ``BackgroundTasks``
        entry after :meth:`start_ingestion` returns.

        Emits events to *progress_callback* (sync or async) with these shapes::

            {"type": "progress",      "job_id": ..., "processed": N, "total": M, "current_file": "..."}
            {"type": "file_complete", "job_id": ..., "file_name": "...", "chunk_count": N}
            {"type": "file_error",    "job_id": ..., "file_name": "...", "error": "..."}
            {"type": "completed",     "job_id": ..., "processed": N, "total": M, "failed": K}

        Parameters
        ----------
        job:
            IngestionJob returned by :meth:`start_ingestion`.
        progress_callback:
            Optional callable invoked with each event dict.  May be async.
        """
        try:
            await self._execute_pipeline(job, progress_callback)
        except Exception as exc:
            log.error(
                "ingestion_pipeline_failed",
                job_id=job.id,
                error=str(exc),
                exc_info=True,
            )
            job.status = "failed"
            job.error_message = str(exc)
            job.completed_at = datetime.now(UTC)
            await self._db.commit()
            raise

    # ------------------------------------------------------------------
    # Private pipeline implementation
    # ------------------------------------------------------------------

    async def _execute_pipeline(
        self,
        job: IngestionJob,
        callback: ProgressCallback | None,
    ) -> None:
        source_folder = job.source_folder

        # --- Scan folder ---
        scanned = _scan_folder(source_folder)
        scanned_by_path = {f.path: f for f in scanned}

        # --- Load all existing Documents from DB ---
        result = await self._db.execute(select(Document))
        existing_docs: dict[str, Document] = {
            doc.file_path: doc for doc in result.scalars().all()
        }

        # --- Classify files ---
        to_process: list[tuple[_ScannedFile, Document, _ChangeReason]] = []
        to_delete: list[Document] = []

        for sfile in scanned:
            if sfile.path in existing_docs:
                doc = existing_docs[sfile.path]
                if doc.status == "completed" and doc.file_hash == sfile.file_hash:
                    log.debug("file_unchanged", file_path=sfile.path)
                    continue
                reason: _ChangeReason = (
                    "modified" if doc.file_hash != sfile.file_hash else "resume"
                )
                doc.file_hash = sfile.file_hash
                doc.file_size_bytes = sfile.file_size_bytes
                doc.status = "pending"
                doc.error_message = None
                to_process.append((sfile, doc, reason))
            else:
                new_doc = Document(
                    file_path=sfile.path,
                    file_name=sfile.file_name,
                    file_type=sfile.extension.lstrip("."),
                    file_hash=sfile.file_hash,
                    file_size_bytes=sfile.file_size_bytes,
                    status="pending",
                )
                self._db.add(new_doc)
                to_process.append((sfile, new_doc, "new"))

        for file_path, doc in existing_docs.items():
            if file_path not in scanned_by_path:
                to_delete.append(doc)

        # --- Update job counters ---
        job.total_files = len(to_process)
        job.new_files = sum(1 for _, _, r in to_process if r == "new")
        job.modified_files = sum(1 for _, _, r in to_process if r == "modified")
        job.deleted_files = len(to_delete)
        await self._db.flush()

        log.info(
            "ingestion_scan_complete",
            job_id=job.id,
            total=len(to_process),
            new=job.new_files,
            modified=job.modified_files,
            deleted=len(to_delete),
        )

        # --- Remove deleted documents ---
        for doc in to_delete:
            log.info(
                "deleting_document",
                file_path=doc.file_path,
                document_id=doc.id,
            )
            await self._vector_store.delete_by_document_id(doc.id)
            await self._db.delete(doc)

        if to_delete:
            await self._db.flush()

        # --- Process each file ---
        for sfile, doc, reason in to_process:
            await self._process_file(job, sfile, doc, reason, callback)
            await self._db.flush()

        # --- Complete job ---
        job.status = "completed"
        job.completed_at = datetime.now(UTC)
        await self._db.commit()

        log.info(
            "ingestion_completed",
            job_id=job.id,
            processed=job.processed_files,
            failed=job.skipped_files,
            deleted=job.deleted_files,
        )

        await _emit(callback, {
            "type": "completed",
            "job_id": job.id,
            "processed": job.processed_files,
            "total": job.total_files,
            "failed": job.skipped_files,
        })

    async def _process_file(
        self,
        job: IngestionJob,
        sfile: _ScannedFile,
        doc: Document,
        reason: _ChangeReason,
        callback: ProgressCallback | None,
    ) -> None:
        log.info(
            "processing_file",
            job_id=job.id,
            file_name=sfile.file_name,
            file_path=sfile.path,
            reason=reason,
        )

        doc.status = "processing"
        await self._db.flush()

        await _emit(callback, {
            "type": "progress",
            "job_id": job.id,
            "processed": job.processed_files,
            "total": job.total_files,
            "current_file": sfile.file_name,
        })

        try:
            # --- Parse ---
            parser = _PARSERS[sfile.extension]
            parsed = await parser.parse(sfile.path)

            # --- Chunk ---
            chunks: list[TextChunk] = self._chunker.chunk(parsed)
            if not chunks:
                raise ValueError(f"Parsing produced no text chunks for {sfile.file_name!r}")

            # --- Delete stale vectors for modified / resume files ---
            if reason in ("modified", "resume"):
                await self._vector_store.delete_by_document_id(doc.id)

            # --- Embed (batch) ---
            texts = [c.text for c in chunks]
            embed_results = await self._embedding_service.embed_batch(texts)

            now_iso = datetime.now(UTC).isoformat()
            chunk_ids = [f"{doc.id}_{c.chunk_index}" for c in chunks]
            embeddings = [r.vector for r in embed_results]
            metadatas = [
                {
                    "document_id": doc.id,
                    "file_name": sfile.file_name,
                    "file_path": sfile.path,
                    "chunk_index": c.chunk_index,
                    "total_chunks": len(chunks),
                    # ChromaDB metadata cannot hold None; use -1 for unknown page
                    "page_number": (
                        c.page_number
                        if c.page_number is not None
                        else _NO_PAGE_NUMBER
                    ),
                    "model_version": r.model_version,
                    "ingested_at": now_iso,
                }
                for c, r in zip(chunks, embed_results)
            ]

            # --- Store vectors in ChromaDB ---
            await self._vector_store.add_chunks(
                chunk_ids=chunk_ids,
                embeddings=embeddings,
                texts=texts,
                metadatas=metadatas,
            )

            # --- Update Document record ---
            doc.status = "completed"
            doc.chunk_count = len(chunks)
            doc.ingested_at = datetime.fromisoformat(now_iso)
            doc.error_message = None
            job.processed_files += 1

            log.info(
                "file_processed",
                job_id=job.id,
                file_name=sfile.file_name,
                chunks=len(chunks),
                model=embed_results[0].model_version,
            )

            await _emit(callback, {
                "type": "file_complete",
                "job_id": job.id,
                "file_name": sfile.file_name,
                "chunk_count": len(chunks),
            })

        except (ParserError, ValueError, AppError) as exc:
            _mark_failed(doc, job, exc)
            log.warning(
                "file_processing_failed",
                job_id=job.id,
                file_name=sfile.file_name,
                error=str(exc),
            )
            await _emit(callback, {
                "type": "file_error",
                "job_id": job.id,
                "file_name": sfile.file_name,
                "error": str(exc),
            })

        except Exception as exc:
            _mark_failed(doc, job, exc)
            log.error(
                "file_processing_error",
                job_id=job.id,
                file_name=sfile.file_name,
                error=str(exc),
                exc_info=True,
            )
            await _emit(callback, {
                "type": "file_error",
                "job_id": job.id,
                "file_name": sfile.file_name,
                "error": str(exc),
            })

    async def _check_no_running_job(self) -> None:
        """Raise :exc:`IngestionConflictError` if a job with ``status='running'`` exists."""
        result = await self._db.execute(
            select(IngestionJob).where(IngestionJob.status == "running").limit(1)
        )
        running_job = result.scalars().first()
        if running_job is not None:
            raise IngestionConflictError(job_id=running_job.id)


# ---------------------------------------------------------------------------
# Private helpers (module-level pure / near-pure functions — easy to test)
# ---------------------------------------------------------------------------


def validate_folder_path(source_folder: str) -> str:
    """Return the resolved absolute path, or raise :exc:`PathValidationError`.

    Public so that tests and routes can call it independently.

    Checks (FR-023)
    ---------------
    1. *source_folder* is non-empty.
    2. The path (after ``os.path.realpath`` symlink resolution) exists.
    3. The resolved path is a directory.
    4. The resolved path is readable by the current process.
    """
    if not source_folder or not source_folder.strip():
        raise PathValidationError(path=source_folder, reason="path must not be empty")

    resolved = os.path.realpath(source_folder)

    if not os.path.exists(resolved):
        raise PathValidationError(path=source_folder, reason="path does not exist")

    if not os.path.isdir(resolved):
        raise PathValidationError(path=source_folder, reason="path is not a directory")

    if not os.access(resolved, os.R_OK):
        raise PathValidationError(path=source_folder, reason="directory is not readable")

    log.info("source_folder_validated", original=source_folder, resolved=resolved)
    return resolved


# Internal alias used by the service
_validate_folder_path = validate_folder_path


def check_disk_space(path: str, min_mb: int) -> None:
    """Raise ``AppError(400)`` if free disk space on *path*'s volume is below *min_mb*.

    Public so that the route can call it for an early 400 before touching the DB.
    Falls back to ``"/"`` when *path* does not yet exist.
    """
    check_path = path if os.path.exists(path) else "/"
    try:
        usage = shutil.disk_usage(check_path)
        free_mb = usage.free / (1024 * 1024)
    except OSError as exc:
        # Can't determine disk usage — log a warning and let the pipeline attempt to proceed
        log.warning("disk_space_check_failed", error=str(exc))
        return

    if free_mb < min_mb:
        raise AppError(
            message=(
                f"Insufficient disk space: {free_mb:.0f} MB free, "
                f"{min_mb} MB required. Free up space and try again."
            ),
            code="insufficient_disk_space",
            status_code=400,
        )

    log.info("disk_space_ok", free_mb=round(free_mb, 1), required_mb=min_mb)


_check_disk_space = check_disk_space


def scan_folder(folder: str) -> list[_ScannedFile]:
    """Recursively scan *folder* and return all supported files.

    Public for testability.  Files with unsupported extensions are skipped
    with a WARNING log entry per FR-016.
    """
    files: list[_ScannedFile] = []
    skipped_count = 0

    for root, _dirs, filenames in os.walk(folder):
        for filename in sorted(filenames):
            ext = Path(filename).suffix.lower()
            abs_path = os.path.join(root, filename)
            resolved_path = os.path.realpath(abs_path)

            if ext not in SUPPORTED_EXTENSIONS:
                log.warning(
                    "unsupported_file_skipped",
                    file_name=filename,
                    extension=ext or "(no extension)",
                )
                skipped_count += 1
                continue

            try:
                file_hash = compute_sha256(resolved_path)
                file_size = os.path.getsize(resolved_path)
            except OSError as exc:
                log.warning(
                    "file_read_error_skipped",
                    file_path=resolved_path,
                    error=str(exc),
                )
                skipped_count += 1
                continue

            files.append(
                _ScannedFile(
                    path=resolved_path,
                    extension=ext,
                    file_hash=file_hash,
                    file_size_bytes=file_size,
                    file_name=filename,
                )
            )

    log.info(
        "folder_scan_complete",
        folder=folder,
        supported_files=len(files),
        skipped_files=skipped_count,
    )
    return files


_scan_folder = scan_folder


def compute_sha256(file_path: str) -> str:
    """Return the SHA-256 hex digest of the file at *file_path*."""
    h = hashlib.sha256()
    with open(file_path, "rb") as fh:  # noqa: PTH123
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _mark_failed(doc: Document, job: IngestionJob, exc: Exception) -> None:
    doc.status = "failed"
    doc.error_message = str(exc)
    doc.chunk_count = 0
    job.skipped_files += 1


async def _emit(
    callback: ProgressCallback | None,
    event: dict[str, Any],
) -> None:
    """Invoke *callback* with *event* — handles both sync and async callables."""
    if callback is None:
        return
    result = callback(event)
    if asyncio.iscoroutine(result):
        await result
