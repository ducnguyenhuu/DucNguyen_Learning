"""Model manager — startup health checks, warm-up, and version tracking.

Responsibilities
----------------
1. **Embedding model warm-up**: Loads the sentence-transformers model on
   startup so the first user request is not delayed.

2. **Ollama connectivity check**: Verifies the Ollama server is reachable
   and the configured LLM model is available.  If the model is not present
   locally, logs a warning and optionally triggers ``ollama pull``.

3. **Model version check (FR-021)**: Compares the ``EMBEDDING_MODEL``
   setting against the ``model_version`` stored in any existing ChromaDB
   vector metadata.  If a mismatch is detected, schedules a background
   re-embedding job.

Usage (called from FastAPI lifespan in ``app.main``)
----------------------------------------------------
::

    manager = ModelManager(vector_store, embedding_provider, llm_provider)
    await manager.startup()
    # … application runs …
    manager.is_reembedding  # True while background re-embed is running
"""
from __future__ import annotations

import asyncio
import subprocess
from typing import Any

import httpx

from app.config import settings
from app.core.exceptions import ModelUnavailableError
from app.core.logging import get_logger
from app.db.vector_store import VectorStore
from app.providers.base import EmbeddingProvider, LLMProvider

log = get_logger(__name__)


class ModelManager:
    """Coordinates model lifecycle for the knowledge-base application."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_provider: EmbeddingProvider,
        llm_provider: LLMProvider,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_provider = embedding_provider
        self._llm_provider = llm_provider
        self.is_reembedding: bool = False
        self._reembed_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------
    # Startup
    # ------------------------------------------------------------------

    async def startup(self) -> None:
        """Full startup sequence — called once in FastAPI lifespan."""
        log.info("model_manager_startup_begin")
        await self._check_ollama_health()
        await self._warmup_embedding_model()
        await self._check_model_version()
        log.info("model_manager_startup_complete")

    # ------------------------------------------------------------------
    # Ollama health check
    # ------------------------------------------------------------------

    async def _check_ollama_health(self) -> None:
        """Verify Ollama is reachable and the LLM model is available.

        Logs a warning (rather than raising) if Ollama is unavailable — the
        application can still serve documents and ingestion; only chat is
        degraded.
        """
        base_url = settings.llm_base_url.rstrip("/")
        model = settings.llm_model

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Check server is alive
                response = await client.get(f"{base_url}/api/tags")
                response.raise_for_status()
                data = response.json()

                available_models = [m.get("name", "") for m in data.get("models", [])]
                if model in available_models:
                    log.info("ollama_model_available", model=model)
                else:
                    log.warning(
                        "ollama_model_not_found",
                        model=model,
                        available=available_models,
                    )
                    await self._pull_ollama_model(model)

        except httpx.ConnectError:
            log.warning(
                "ollama_unreachable",
                url=base_url,
                hint="Start Ollama with: ollama serve",
            )
        except Exception as exc:
            log.warning("ollama_health_check_failed", error=str(exc))

    async def _pull_ollama_model(self, model: str) -> None:
        """Trigger ``ollama pull <model>`` in a non-blocking subprocess (FR-014)."""
        log.info("ollama_pull_starting", model=model)
        try:
            proc = await asyncio.create_subprocess_exec(
                "ollama",
                "pull",
                model,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            asyncio.get_event_loop().create_task(proc.wait())
        except FileNotFoundError:
            log.warning("ollama_not_installed", hint="Install from https://ollama.com")
        except Exception as exc:
            log.warning("ollama_pull_failed", model=model, error=str(exc))

    # ------------------------------------------------------------------
    # Embedding model warm-up
    # ------------------------------------------------------------------

    async def _warmup_embedding_model(self) -> None:
        """Run a dummy embed call to load the sentence-transformers model."""
        log.info("embedding_warmup_start", model=settings.embedding_model)
        try:
            await self._embedding_provider.embed("warm-up")
            log.info("embedding_warmup_complete", model=settings.embedding_model)
        except ModelUnavailableError as exc:
            log.warning("embedding_warmup_failed", error=str(exc))
        except Exception as exc:
            log.warning("embedding_warmup_error", error=str(exc))

    # ------------------------------------------------------------------
    # FR-021 Model version check
    # ------------------------------------------------------------------

    async def _check_model_version(self) -> None:
        """Compare stored embedding model version in ChromaDB with config.

        If a mismatch is detected, schedule a background re-embedding job.
        """
        configured_model = self._embedding_provider.model_version
        stored_version = await self._vector_store.get_any_model_version()

        if stored_version is None:
            # Collection is empty — nothing to re-embed
            log.info(
                "model_version_check_skip",
                reason="empty_collection",
                configured_model=configured_model,
            )
            return

        if stored_version == configured_model:
            log.info(
                "model_version_check_ok",
                model=configured_model,
            )
            return

        log.warning(
            "model_version_mismatch_detected",
            stored=stored_version,
            configured=configured_model,
        )
        log.info("reembed_job_scheduled")
        self.is_reembedding = True
        self._reembed_task = asyncio.create_task(
            self._run_reembed_background(stored_version, configured_model)
        )

    # ------------------------------------------------------------------
    # Background re-embedding (FR-021)
    # ------------------------------------------------------------------

    async def _run_reembed_background(
        self, stored_version: str, configured_model: str
    ) -> None:
        """Create an IngestionJob(trigger_reason='reembed') and run the pipeline.

        Called as an asyncio background task when a model-version mismatch is
        detected at startup.  Broadcasts a ``reembed_started`` WS event so any
        connected frontend clients can react immediately (FR-021).

        Sets :attr:`is_reembedding` to ``False`` when the pipeline finishes
        (success or failure) so ``GET /health`` reflects the correct state.
        """
        # Late imports to avoid circular dependency:
        # model_manager ← services ← api/routes would be circular.
        from app.api.routes.ingestion import _subscriptions, broadcast_event
        from app.db.database import get_session
        from app.parsers import Chunker
        from app.services.embedding import EmbeddingService
        from app.services.ingestion import IngestionService

        source_folder = settings.knowledge_folder
        if not source_folder:
            log.warning(
                "reembed_skipped",
                reason="knowledge_folder_not_configured",
            )
            self.is_reembedding = False
            return

        try:
            async with get_session() as db:
                embed_svc = EmbeddingService(self._embedding_provider)
                chunker = Chunker.from_settings(settings)
                svc = IngestionService(
                    db=db,
                    vector_store=self._vector_store,
                    embedding_service=embed_svc,
                    chunker=chunker,
                )

                job = await svc.start_ingestion(
                    source_folder, trigger_reason="reembed"
                )
                await db.commit()
                job_id = job.id

                log.info(
                    "reembed_job_created",
                    job_id=job_id,
                    stored_model=stored_version,
                    configured_model=configured_model,
                )

                # Emit reembed_started to any already-connected WS clients
                reembed_event: dict[str, object] = {
                    "type": "reembed_started",
                    "job_id": job_id,
                    "reason": (
                        f"Embedding model changed from {stored_version} "
                        f"to {configured_model}"
                    ),
                    "total_files": job.total_files,
                }
                broadcast_event(job_id, reembed_event)

                async def _broadcast(event: dict[str, Any]) -> None:
                    for queue in list(_subscriptions.get(job_id, [])):
                        await queue.put(event)

                try:
                    await svc.run_pipeline(job, progress_callback=_broadcast)
                    log.info("reembed_pipeline_complete", job_id=job_id)
                except Exception as exc:
                    log.error(
                        "reembed_pipeline_failed",
                        job_id=job_id,
                        error=str(exc),
                        exc_info=True,
                    )
                finally:
                    # Signal WS subscribers the pipeline has ended
                    for queue in list(_subscriptions.get(job_id, [])):
                        await queue.put({"type": "_done_"})
                    _subscriptions.pop(job_id, None)

        except Exception as exc:
            log.error(
                "reembed_job_create_failed",
                error=str(exc),
                exc_info=True,
            )
        finally:
            self.is_reembedding = False
            log.info("reembed_finished", is_reembedding=self.is_reembedding)

    # ------------------------------------------------------------------
    # Shared health status for GET /health
    # ------------------------------------------------------------------

    async def health_status(self) -> dict[str, object]:
        """Return a dict of component statuses for the /health endpoint."""
        base_url = settings.llm_base_url.rstrip("/")
        ollama_ok = False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{base_url}/api/tags")
                ollama_ok = r.status_code == 200
        except Exception:
            pass

        return {
            "status": "ok",
            "database": "ok",  # if we reach here, DB started successfully
            "embedding_model": settings.embedding_model,
            "llm_model": settings.llm_model,
            "ollama": "ok" if ollama_ok else "unavailable",
            "reembedding": self.is_reembedding,
        }
