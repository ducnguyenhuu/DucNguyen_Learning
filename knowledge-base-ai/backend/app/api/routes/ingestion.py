"""Ingestion routes — REST (§1.1, §1.2) + WebSocket (§1.3).

Route contracts: api-contracts.md
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import DbSession, EmbProvider, VStore
from app.config import settings
from app.core.exceptions import IngestionJobNotFoundError, PathValidationError
from app.core.logging import get_logger
from app.models.ingestion_job import IngestionJob
from app.parsers import Chunker
from app.services.embedding import EmbeddingService
from app.services.ingestion import IngestionService

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# WebSocket subscription registry
# job_id → list of per-client queues.  Pure asyncio — no lock needed.
# ---------------------------------------------------------------------------
_subscriptions: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}


def broadcast_event(job_id: str, event: dict[str, Any]) -> None:
    """Push *event* to every WS queue currently subscribed to *job_id*.

    Fire-and-forget: uses ``put_nowait`` so it is safe to call from sync or
    async contexts.  Called by :class:`~app.services.model_manager.ModelManager`
    to emit ``reembed_started`` events at startup (FR-021).
    """
    for queue in list(_subscriptions.get(job_id, [])):
        queue.put_nowait(event)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class StartIngestionRequest(BaseModel):
    """Body for POST /ingestion/start."""

    source_folder: Optional[str] = Field(
        default=None,
        description="Absolute path to the documents folder. "
        "Defaults to the configured knowledge_folder if omitted.",
    )


class StartIngestionResponse(BaseModel):
    """202 response body for POST /ingestion/start."""

    job_id: str
    status: str
    total_files: int
    source_folder: str
    started_at: datetime


class IngestionStatusResponse(BaseModel):
    """200 response body for GET /ingestion/status/{job_id}."""

    job_id: str
    status: str
    total_files: int
    processed_files: int
    new_files: int
    modified_files: int
    deleted_files: int
    skipped_files: int
    source_folder: str
    started_at: datetime
    completed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Background task runner (owns its own DB session)
# ---------------------------------------------------------------------------


async def _run_pipeline_in_background(job_id: str) -> None:
    """Background task: fetch the job and run the full ingestion pipeline.

    Creates its own DB session so it is not bound to the HTTP request
    session (which closes when the 202 response is sent).  Broadcasts
    progress events to any connected WebSocket subscribers.
    """
    from app.api.deps import get_singleton_embedding_provider, get_singleton_vector_store
    from app.db.database import get_session

    async def _broadcast(event: dict[str, Any]) -> None:
        """Push *event* to every WS queue subscribed to this job."""
        for queue in list(_subscriptions.get(job_id, [])):
            await queue.put(event)

    async with get_session() as db:
        result = await db.execute(
            select(IngestionJob).where(IngestionJob.id == job_id)
        )
        job = result.scalars().first()
        if job is None:
            log.error("background_job_not_found", job_id=job_id)
            return

        embed_svc = EmbeddingService(get_singleton_embedding_provider())
        chunker = Chunker.from_settings(settings)
        svc = IngestionService(
            db=db,
            vector_store=get_singleton_vector_store(),
            embedding_service=embed_svc,
            chunker=chunker,
        )
        try:
            await svc.run_pipeline(job, progress_callback=_broadcast)
        except Exception:
            # run_pipeline already committed the failure status and logged the error
            pass
        finally:
            # Signal all WS subscribers that the pipeline has ended.
            for queue in list(_subscriptions.get(job_id, [])):
                await queue.put({"type": "_done_"})
            _subscriptions.pop(job_id, None)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/start",
    status_code=202,
    summary="Start document ingestion (FR-005, FR-022, FR-023)",
    response_model=StartIngestionResponse,
)
async def start_ingestion(
    body: StartIngestionRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
    vector_store: VStore,
    embedding_provider: EmbProvider,
) -> StartIngestionResponse:
    """Trigger ingestion from the knowledge folder.

    Pre-flight checks performed synchronously before returning 202:
    - Disk space validation (400 if insufficient)
    - Path validation — existence, directory, readable, symlink resolved (400)
    - Single-job enforcement — 409 if a job is already running

    The actual parse → chunk → embed → store pipeline runs as a background
    task after the 202 is returned to the client.
    """
    source_folder = body.source_folder or settings.knowledge_folder
    if not source_folder:
        raise PathValidationError(
            path="",
            reason="no source_folder provided and knowledge_folder is not configured",
        )

    embed_svc = EmbeddingService(embedding_provider)
    chunker = Chunker.from_settings(settings)

    svc = IngestionService(
        db=db,
        vector_store=vector_store,
        embedding_service=embed_svc,
        chunker=chunker,
    )

    job = await svc.start_ingestion(source_folder)
    await db.commit()

    background_tasks.add_task(_run_pipeline_in_background, job.id)

    log.info(
        "ingestion_start_accepted",
        job_id=job.id,
        source_folder=job.source_folder,
    )

    return StartIngestionResponse(
        job_id=job.id,
        status=job.status,
        total_files=job.total_files,
        source_folder=job.source_folder,
        started_at=job.started_at,
    )


@router.get(
    "/status/{job_id}",
    summary="Get ingestion job status",
    response_model=IngestionStatusResponse,
)
async def get_ingestion_status(
    job_id: str,
    db: DbSession,
) -> IngestionStatusResponse:
    """Return the current status of an ingestion job.

    Raises 404 if the job_id does not exist.
    """
    result = await db.execute(
        select(IngestionJob).where(IngestionJob.id == job_id)
    )
    job = result.scalars().first()

    if job is None:
        raise IngestionJobNotFoundError(job_id=job_id)

    return IngestionStatusResponse(
        job_id=job.id,
        status=job.status,
        total_files=job.total_files,
        processed_files=job.processed_files,
        new_files=job.new_files,
        modified_files=job.modified_files,
        deleted_files=job.deleted_files,
        skipped_files=job.skipped_files,
        source_folder=job.source_folder,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


# ---------------------------------------------------------------------------
# WebSocket: real-time ingestion progress
# ---------------------------------------------------------------------------

_WS_KEEPALIVE_TIMEOUT = 30  # seconds before sending a keepalive ping


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    """Translate internal service event field names to api-contracts.md §1.3 names.

    The IngestionService emits abbreviated keys (``processed``, ``total``,
    ``chunk_count``); the contract specifies ``processed_files``,
    ``total_files``, ``chunks_created``.  Any extra/unknown keys are passed
    through unchanged.
    """
    out = dict(event)
    # progress event
    if "processed" in out:
        out["processed_files"] = out.pop("processed")
    if "total" in out:
        out["total_files"] = out.pop("total")
    # file_complete event
    if "chunk_count" in out:
        out["chunks_created"] = out.pop("chunk_count")
    # Strip internal-only keys
    out.pop("job_id", None)  # contract omits job_id on nested events; harmless to include
    out["job_id"] = event.get("job_id", "")
    return out


def _terminal_event_from_job(job: IngestionJob) -> dict[str, Any]:
    """Build a §1.3 'completed' or 'failed' event from a DB job row."""
    duration = None
    if job.completed_at and job.started_at:
        duration = (job.completed_at - job.started_at).total_seconds()
    return {
        "type": job.status,  # "completed" or "failed"
        "job_id": job.id,
        "total_files": job.total_files,
        "new_files": job.new_files,
        "modified_files": job.modified_files,
        "deleted_files": job.deleted_files,
        "skipped_files": job.skipped_files,
        "duration_seconds": duration,
    }


@router.websocket("/progress/{job_id}")
async def ingestion_progress_ws(
    websocket: WebSocket,
    job_id: str,
) -> None:
    """Stream real-time ingestion progress events for *job_id* (§1.3).

    Message types sent to the client:
    - ``progress``       — periodic update while files are being processed
    - ``file_complete``  — a file finished successfully
    - ``file_error``     — a file failed to process
    - ``completed``      — the entire job finished
    - ``failed``         — the job itself failed catastrophically
    - ``error``          — job not found (WS closes immediately after)
    - ``keepalive``      — sent every 30 s while waiting for events

    The connection closes automatically once a terminal event is emitted.
    """
    from app.db.database import get_session

    await websocket.accept()

    # ---- Look up job -------------------------------------------------------
    async with get_session() as db:
        result = await db.execute(
            select(IngestionJob).where(IngestionJob.id == job_id)
        )
        job: IngestionJob | None = result.scalars().first()

    if job is None:
        await websocket.send_json({
            "type": "error",
            "code": "not_found",
            "message": f"Ingestion job '{job_id}' not found.",
        })
        await websocket.close(code=1008)
        return

    # ---- Already finished — send terminal event and close ------------------
    if job.status in ("completed", "failed"):
        await websocket.send_json(_terminal_event_from_job(job))
        await websocket.close()
        return

    # ---- Subscribe to live events from the running background task ----------
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _subscriptions.setdefault(job_id, []).append(queue)

    log.info("ws_progress_subscribed", job_id=job_id)

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=_WS_KEEPALIVE_TIMEOUT)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "keepalive"})
                continue

            # Internal sentinel — background task is done
            if event.get("type") == "_done_":
                break

            # Normalize field names to match §1.3 and relay to client
            await websocket.send_json(_normalize_event(event))

            # Close after the terminal event so the client can receive it
            if event.get("type") in ("completed", "failed"):
                break

    except WebSocketDisconnect:
        log.info("ws_progress_client_disconnected", job_id=job_id)
    except Exception:
        log.exception("ws_progress_error", job_id=job_id)
    finally:
        # Remove this client's queue from the registry
        subs = _subscriptions.get(job_id, [])
        try:
            subs.remove(queue)
        except ValueError:
            pass
        if not subs:
            _subscriptions.pop(job_id, None)

        try:
            await websocket.close()
        except Exception:
            pass

        log.info("ws_progress_closed", job_id=job_id)
