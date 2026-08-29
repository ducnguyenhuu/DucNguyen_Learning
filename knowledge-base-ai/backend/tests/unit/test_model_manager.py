"""Unit tests for ModelManager — T066 (FR-021 model version check + reembed trigger).

Coverage:
- _check_model_version: empty collection skip, version-match skip, mismatch → task
- _run_reembed_background: no folder skip, happy path, ingestion failure, event shape
- health_status: reembedding field reflects is_reembedding flag
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.model_manager import ModelManager

# ---------------------------------------------------------------------------
# Patch targets
# _run_reembed_background uses late `from X import Y` — we must patch the
# originating module so each `from X import Y` inside the method picks up
# the mock when Python resolves `sys.modules['X'].Y`.
# settings is a module-level import in model_manager, so patch there.
# ---------------------------------------------------------------------------
_PT_SETTINGS = "app.services.model_manager.settings"
_PT_GET_SESSION = "app.db.database.get_session"
_PT_INGESTION_SVC = "app.services.ingestion.IngestionService"
_PT_EMBEDDING_SVC = "app.services.embedding.EmbeddingService"
_PT_CHUNKER = "app.parsers.Chunker"
_PT_BROADCAST = "app.api.routes.ingestion.broadcast_event"
_PT_SUBSCRIPTIONS = "app.api.routes.ingestion._subscriptions"


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------


def _make_manager(
    stored_version: str | None = None,
    configured_model: str = "nomic-embed-text-v1.5",
) -> tuple[ModelManager, MagicMock, MagicMock, MagicMock]:
    """Create a ModelManager with lightweight stubs."""
    mock_vs = MagicMock()
    mock_vs.get_any_model_version = AsyncMock(return_value=stored_version)

    mock_embed = MagicMock()
    mock_embed.model_version = configured_model
    mock_embed.embed = AsyncMock(return_value=[0.1] * 768)

    mock_llm = MagicMock()

    manager = ModelManager(
        vector_store=mock_vs,
        embedding_provider=mock_embed,
        llm_provider=mock_llm,
    )
    return manager, mock_vs, mock_embed, mock_llm


def _make_session_cm(mock_db: AsyncMock):
    """Return an async context manager factory that yields mock_db."""

    @asynccontextmanager
    async def _cm():
        yield mock_db

    return _cm


def _reembed_patches(
    knowledge_folder: str = "/data/docs",
    mock_job: MagicMock | None = None,
    start_exc: Exception | None = None,
    pipeline_exc: Exception | None = None,
    captured_broadcasts: list | None = None,
):
    """Context manager factory that patches all deps of _run_reembed_background."""
    if mock_job is None:
        mock_job = MagicMock()
        mock_job.id = "job-reembed-1"
        mock_job.total_files = 5

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_svc = MagicMock()
    if start_exc:
        mock_svc.start_ingestion = AsyncMock(side_effect=start_exc)
    else:
        mock_svc.start_ingestion = AsyncMock(return_value=mock_job)

    if pipeline_exc:
        mock_svc.run_pipeline = AsyncMock(side_effect=pipeline_exc)
    else:
        mock_svc.run_pipeline = AsyncMock()

    if captured_broadcasts is not None:
        def _broadcast(job_id: str, event: dict) -> None:
            captured_broadcasts.append((job_id, event))
        mock_broadcast = _broadcast
    else:
        mock_broadcast = MagicMock()

    class _Stack:
        def __init__(self) -> None:
            self.mock_job = mock_job
            self.mock_db = mock_db
            self.mock_svc = mock_svc
            self.mock_broadcast = mock_broadcast
            self._patches: list = []

        def __enter__(self) -> _Stack:
            import unittest.mock as um

            mock_cfg = MagicMock()
            mock_cfg.knowledge_folder = knowledge_folder

            self._patches = [
                um.patch(_PT_SETTINGS, mock_cfg),
                um.patch(_PT_GET_SESSION, _make_session_cm(mock_db)),
                um.patch(_PT_INGESTION_SVC, return_value=mock_svc),
                um.patch(_PT_EMBEDDING_SVC),
                um.patch(_PT_CHUNKER),
                um.patch(_PT_BROADCAST, mock_broadcast),
                um.patch(_PT_SUBSCRIPTIONS, {}),
            ]
            for p in self._patches:
                p.__enter__()
            return self

        def __exit__(self, *args) -> None:
            for p in reversed(self._patches):
                p.__exit__(*args)

    return _Stack()


# ---------------------------------------------------------------------------
# _check_model_version
# ---------------------------------------------------------------------------


class TestCheckModelVersion:
    @pytest.mark.asyncio
    async def test_empty_collection_skips_reembed(self) -> None:
        """stored_version=None → is_reembedding stays False, no task created."""
        manager, *_ = _make_manager(stored_version=None)
        await manager._check_model_version()
        assert manager.is_reembedding is False
        assert manager._reembed_task is None

    @pytest.mark.asyncio
    async def test_version_match_skips_reembed(self) -> None:
        """Same stored and configured version → no background task."""
        manager, *_ = _make_manager(
            stored_version="nomic-embed-text-v1.5",
            configured_model="nomic-embed-text-v1.5",
        )
        await manager._check_model_version()
        assert manager.is_reembedding is False
        assert manager._reembed_task is None

    @pytest.mark.asyncio
    async def test_version_mismatch_sets_reembedding_flag(self) -> None:
        """Version mismatch → is_reembedding=True after _check_model_version."""
        manager, *_ = _make_manager(
            stored_version="nomic-embed-text-v1.5",
            configured_model="nomic-embed-text-v2.0",
        )
        manager._run_reembed_background = AsyncMock()  # type: ignore[method-assign]
        await manager._check_model_version()
        assert manager.is_reembedding is True

    @pytest.mark.asyncio
    async def test_version_mismatch_creates_task(self) -> None:
        """Version mismatch → asyncio.Task stored in _reembed_task."""
        manager, *_ = _make_manager(
            stored_version="old-model",
            configured_model="new-model",
        )
        manager._run_reembed_background = AsyncMock()  # type: ignore[method-assign]
        await manager._check_model_version()
        assert manager._reembed_task is not None
        await manager._reembed_task

    @pytest.mark.asyncio
    async def test_version_mismatch_passes_correct_versions(self) -> None:
        """Background coroutine called with (stored_version, configured_model)."""
        manager, *_ = _make_manager(stored_version="v1.5", configured_model="v2.0")
        bg_mock = AsyncMock()
        manager._run_reembed_background = bg_mock  # type: ignore[method-assign]
        await manager._check_model_version()
        await manager._reembed_task
        bg_mock.assert_awaited_once_with("v1.5", "v2.0")


# ---------------------------------------------------------------------------
# _run_reembed_background
# ---------------------------------------------------------------------------


class TestRunReembedBackground:
    @pytest.mark.asyncio
    async def test_no_knowledge_folder_resets_flag(self) -> None:
        """Empty knowledge_folder → is_reembedding reset to False, no job."""
        manager, *_ = _make_manager()
        manager.is_reembedding = True

        with _reembed_patches(knowledge_folder="") as ctx:
            await manager._run_reembed_background("v1", "v2")

        assert manager.is_reembedding is False
        ctx.mock_svc.start_ingestion.assert_not_called()

    @pytest.mark.asyncio
    async def test_happy_path_calls_start_ingestion_with_reembed_reason(self) -> None:
        """Happy path: start_ingestion called with trigger_reason='reembed'."""
        manager, *_ = _make_manager()
        manager.is_reembedding = True

        with _reembed_patches() as ctx:
            await manager._run_reembed_background("v1", "v2")

        ctx.mock_svc.start_ingestion.assert_awaited_once()
        call = ctx.mock_svc.start_ingestion.call_args
        # trigger_reason may be positional or keyword
        passed_reason = call.kwargs.get("trigger_reason") or (
            call.args[1] if len(call.args) > 1 else None
        )
        assert passed_reason == "reembed"

    @pytest.mark.asyncio
    async def test_happy_path_calls_run_pipeline(self) -> None:
        """Happy path: run_pipeline called after job is created."""
        manager, *_ = _make_manager()
        manager.is_reembedding = True

        with _reembed_patches() as ctx:
            await manager._run_reembed_background("v1", "v2")

        ctx.mock_svc.run_pipeline.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_happy_path_resets_reembedding_flag(self) -> None:
        """is_reembedding is False after successful pipeline run."""
        manager, *_ = _make_manager()
        manager.is_reembedding = True

        with _reembed_patches():
            await manager._run_reembed_background("v1", "v2")

        assert manager.is_reembedding is False

    @pytest.mark.asyncio
    async def test_broadcasts_reembed_started_event(self) -> None:
        """reembed_started WS event is broadcast with correct type field."""
        captured: list = []
        manager, *_ = _make_manager()
        manager.is_reembedding = True

        with _reembed_patches(captured_broadcasts=captured):
            await manager._run_reembed_background("v1", "v2")

        assert len(captured) == 1
        job_id, event = captured[0]
        assert event["type"] == "reembed_started"

    @pytest.mark.asyncio
    async def test_reembed_event_includes_job_id(self) -> None:
        """reembed_started event contains job.id."""
        captured: list = []
        mock_job = MagicMock()
        mock_job.id = "job-reembed-99"
        mock_job.total_files = 3

        manager, *_ = _make_manager()
        manager.is_reembedding = True

        with _reembed_patches(mock_job=mock_job, captured_broadcasts=captured):
            await manager._run_reembed_background("v1", "v2")

        _, event = captured[0]
        assert event["job_id"] == "job-reembed-99"

    @pytest.mark.asyncio
    async def test_reembed_event_reason_mentions_both_versions(self) -> None:
        """Reason string mentions both old and new model names."""
        captured: list = []
        manager, *_ = _make_manager()
        manager.is_reembedding = True

        with _reembed_patches(captured_broadcasts=captured):
            await manager._run_reembed_background("old-model-v1", "new-model-v2")

        _, event = captured[0]
        assert "old-model-v1" in event["reason"]
        assert "new-model-v2" in event["reason"]

    @pytest.mark.asyncio
    async def test_reembed_event_total_files_matches_job(self) -> None:
        """reembed_started total_files equals job.total_files."""
        captured: list = []
        mock_job = MagicMock()
        mock_job.id = "job-tf-99"
        mock_job.total_files = 17

        manager, *_ = _make_manager()
        manager.is_reembedding = True

        with _reembed_patches(mock_job=mock_job, captured_broadcasts=captured):
            await manager._run_reembed_background("v1", "v2")

        _, event = captured[0]
        assert event["total_files"] == 17

    @pytest.mark.asyncio
    async def test_start_ingestion_failure_resets_flag(self) -> None:
        """If start_ingestion raises, is_reembedding resets to False."""
        manager, *_ = _make_manager()
        manager.is_reembedding = True

        with _reembed_patches(start_exc=RuntimeError("disk full")):
            await manager._run_reembed_background("v1", "v2")

        assert manager.is_reembedding is False

    @pytest.mark.asyncio
    async def test_pipeline_failure_resets_flag(self) -> None:
        """If run_pipeline raises, is_reembedding resets to False."""
        manager, *_ = _make_manager()
        manager.is_reembedding = True

        with _reembed_patches(pipeline_exc=RuntimeError("parse error")):
            await manager._run_reembed_background("v1", "v2")

        assert manager.is_reembedding is False


# ---------------------------------------------------------------------------
# health_status
# ---------------------------------------------------------------------------


class TestHealthStatus:
    def _mock_httpx(self, ok: bool = True):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 200 if ok else 503
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=mock_resp
            if ok
            else AsyncMock(side_effect=httpx.ConnectError("refused"))
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        return patch("app.services.model_manager.httpx.AsyncClient", return_value=mock_client)

    @pytest.mark.asyncio
    async def test_reembedding_false_when_idle(self) -> None:
        """health_status reembedding=False when not re-embedding."""
        manager, *_ = _make_manager()
        manager.is_reembedding = False

        with self._mock_httpx():
            status = await manager.health_status()

        assert status["reembedding"] is False

    @pytest.mark.asyncio
    async def test_reembedding_true_while_running(self) -> None:
        """health_status reembedding=True while re-embedding in progress."""
        manager, *_ = _make_manager()
        manager.is_reembedding = True

        with self._mock_httpx():
            status = await manager.health_status()

        assert status["reembedding"] is True

    @pytest.mark.asyncio
    async def test_status_ok_always_present(self) -> None:
        manager, *_ = _make_manager()

        with self._mock_httpx():
            status = await manager.health_status()

        assert status["status"] == "ok"

    @pytest.mark.asyncio
    async def test_ollama_unavailable_on_connect_error(self) -> None:
        """health_status ollama=unavailable when Ollama is unreachable."""
        import httpx

        manager, *_ = _make_manager()

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.model_manager.httpx.AsyncClient", return_value=mock_client):
            status = await manager.health_status()

        assert status["ollama"] == "unavailable"



# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------
