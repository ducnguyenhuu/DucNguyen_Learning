"""Unit tests for ingestion REST routes.

Tests HTTP contracts per api-contracts.md §1.1 and §1.2:
- POST /api/v1/ingestion/start → 202 / 400 / 409 / 422
- GET  /api/v1/ingestion/status/{job_id} → 200 / 404

All database, vector store, and embedding provider dependencies are
replaced with lightweight mocks via FastAPI dependency overrides so
these tests run without a real DB or model infrastructure.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db_session, get_embedding_provider, get_vector_store
from app.core.exceptions import AppError
from app.core.logging import configure_logging
from app.main import app
from app.models.ingestion_job import IngestionJob
from app.providers.base import EmbeddingProvider

# Configure structlog once so the lifespan log.info() calls don't hit
# the default PrintLogger (which has no .name attribute).
configure_logging(level="WARNING", fmt="console")


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 3, 4, 12, 0, 0, tzinfo=UTC)


def _make_job(
    *,
    id: str = "job-abc",
    status: str = "running",
    source_folder: str = "/tmp/docs",
    total_files: int = 0,
    processed_files: int = 0,
    new_files: int = 0,
    modified_files: int = 0,
    deleted_files: int = 0,
    skipped_files: int = 0,
    completed_at: datetime | None = None,
) -> IngestionJob:
    job = IngestionJob(
        id=id,
        source_folder=source_folder,
        trigger_reason="user",
        status=status,
        total_files=total_files,
        processed_files=processed_files,
        new_files=new_files,
        modified_files=modified_files,
        deleted_files=deleted_files,
        skipped_files=skipped_files,
        started_at=_NOW,
    )
    job.completed_at = completed_at
    return job


class _StubProvider(EmbeddingProvider):
    async def embed(self, text: str) -> list[float]:
        return [0.0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] for _ in texts]

    @property
    def model_version(self) -> str:
        return "test-model"

    @property
    def dimensions(self) -> int:
        return 1


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> AsyncMock:
    """A mock AsyncSession with no running jobs and no existing documents."""
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    return db


@pytest.fixture
def client(mock_db: AsyncMock) -> TestClient:
    """TestClient with all external dependencies overridden.

    Patches out the lifespan's heavy startup calls (init_db, init_singletons,
    ModelManager.startup) so tests run without a real DB or model infra.
    """

    async def _override_db() -> AsyncGenerator:
        yield mock_db

    def _override_vs() -> MagicMock:
        vs = MagicMock()
        vs.delete_by_document_id = AsyncMock()
        vs.add_chunks = AsyncMock()
        return vs

    def _override_embed() -> _StubProvider:
        return _StubProvider()

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_vector_store] = _override_vs
    app.dependency_overrides[get_embedding_provider] = _override_embed

    with (
        patch("app.main.init_db", return_value=AsyncMock()),
        patch("app.main.init_singletons"),
        patch("app.main.close_db", return_value=AsyncMock()),
        patch("app.main.get_singleton_vector_store", return_value=MagicMock()),
        patch("app.main.get_singleton_embedding_provider", return_value=MagicMock()),
        patch("app.main.get_singleton_llm_provider", return_value=MagicMock()),
        patch("app.services.model_manager.ModelManager.startup", new_callable=AsyncMock),
        patch("app.api.routes.ingestion._run_pipeline_in_background"),
    ):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/ingestion/start — happy path
# ---------------------------------------------------------------------------


class TestStartIngestionHappyPath:
    def test_returns_202(self, client: TestClient, tmp_path: object) -> None:
        resp = client.post(
            "/api/v1/ingestion/start",
            json={"source_folder": str(tmp_path)},
        )
        assert resp.status_code == 202

    def test_response_has_job_id(self, client: TestClient, tmp_path: object) -> None:
        resp = client.post(
            "/api/v1/ingestion/start",
            json={"source_folder": str(tmp_path)},
        )
        body = resp.json()
        assert "job_id" in body
        assert isinstance(body["job_id"], str)

    def test_response_status_is_running(self, client: TestClient, tmp_path: object) -> None:
        resp = client.post(
            "/api/v1/ingestion/start",
            json={"source_folder": str(tmp_path)},
        )
        assert resp.json()["status"] == "running"

    def test_response_source_folder_is_resolved(
        self, client: TestClient, tmp_path: object
    ) -> None:
        import os

        resp = client.post(
            "/api/v1/ingestion/start",
            json={"source_folder": str(tmp_path)},
        )
        expected = os.path.realpath(str(tmp_path))
        assert resp.json()["source_folder"] == expected

    def test_response_has_started_at(self, client: TestClient, tmp_path: object) -> None:
        resp = client.post(
            "/api/v1/ingestion/start",
            json={"source_folder": str(tmp_path)},
        )
        assert "started_at" in resp.json()

    def test_request_id_header_present(self, client: TestClient, tmp_path: object) -> None:
        resp = client.post(
            "/api/v1/ingestion/start",
            json={"source_folder": str(tmp_path)},
        )
        assert "x-request-id" in resp.headers


# ---------------------------------------------------------------------------
# POST /api/v1/ingestion/start — error cases
# ---------------------------------------------------------------------------


class TestStartIngestionErrors:
    def test_nonexistent_path_returns_422(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingestion/start",
            json={"source_folder": "/nonexistent/ghost/folder"},
        )
        assert resp.status_code == 422

    def test_nonexistent_path_error_code(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/ingestion/start",
            json={"source_folder": "/nonexistent/ghost/folder"},
        )
        assert resp.json()["error"]["code"] == "path_validation_error"

    def test_file_path_returns_422(self, client: TestClient, tmp_path: object) -> None:
        f = tmp_path / "file.txt"
        f.write_text("hello")
        resp = client.post(
            "/api/v1/ingestion/start",
            json={"source_folder": str(f)},
        )
        assert resp.status_code == 422

    def test_conflict_returns_409(
        self, tmp_path: object, mock_db: AsyncMock
    ) -> None:
        """Returns 409 when a running job already exists."""
        running_job = _make_job(id="existing", status="running")
        # Override execute to return the running job for conflict check
        conflict_result = MagicMock()
        conflict_result.scalars.return_value.first.return_value = running_job
        mock_db.execute = AsyncMock(return_value=conflict_result)

        async def _override_db() -> AsyncGenerator:
            yield mock_db

        def _override_vs() -> MagicMock:
            return MagicMock()

        def _override_embed() -> _StubProvider:
            return _StubProvider()

        app.dependency_overrides[get_db_session] = _override_db
        app.dependency_overrides[get_vector_store] = _override_vs
        app.dependency_overrides[get_embedding_provider] = _override_embed

        try:
            with (
                patch("app.main.init_db", return_value=AsyncMock()),
                patch("app.main.init_singletons"),
                patch("app.main.close_db", return_value=AsyncMock()),
                patch("app.main.get_singleton_vector_store", return_value=MagicMock()),
                patch("app.main.get_singleton_embedding_provider", return_value=MagicMock()),
                patch("app.main.get_singleton_llm_provider", return_value=MagicMock()),
                patch("app.services.model_manager.ModelManager.startup", new_callable=AsyncMock),
                patch("app.api.routes.ingestion._run_pipeline_in_background"),
            ):
                with TestClient(app, raise_server_exceptions=False) as c:
                    resp = c.post(
                        "/api/v1/ingestion/start",
                        json={"source_folder": str(tmp_path)},
                    )
            assert resp.status_code == 409
            assert resp.json()["error"]["code"] == "ingestion_conflict"
        finally:
            app.dependency_overrides.clear()

    def test_no_folder_configured_returns_422(self, client: TestClient) -> None:
        """Returns 422 when source_folder omitted and knowledge_folder is not set."""
        with patch("app.api.routes.ingestion.settings") as mock_settings:
            mock_settings.knowledge_folder = ""
            resp = client.post("/api/v1/ingestion/start", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/ingestion/status/{job_id}
# ---------------------------------------------------------------------------


class TestGetIngestionStatus:
    def _build_client_with_job(self, job: IngestionJob | None) -> TestClient:
        """Build a TestClient whose DB mock returns *job* for every execute call."""
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.first.return_value = job
        db.execute = AsyncMock(return_value=result)

        async def _override_db() -> AsyncGenerator:
            yield db

        app.dependency_overrides[get_db_session] = _override_db
        app.dependency_overrides[get_vector_store] = lambda: MagicMock()
        app.dependency_overrides[get_embedding_provider] = lambda: _StubProvider()

        patches = [
            patch("app.main.init_db", return_value=AsyncMock()),
            patch("app.main.init_singletons"),
            patch("app.main.close_db", return_value=AsyncMock()),
            patch("app.main.get_singleton_vector_store", return_value=MagicMock()),
            patch("app.main.get_singleton_embedding_provider", return_value=MagicMock()),
            patch("app.main.get_singleton_llm_provider", return_value=MagicMock()),
            patch(
                "app.services.model_manager.ModelManager.startup",
                new_callable=AsyncMock,
            ),
        ]
        for p in patches:
            p.start()
        self._active_patches = patches
        return TestClient(app, raise_server_exceptions=False)

    def teardown_method(self) -> None:  # noqa: D102
        for p in getattr(self, "_active_patches", []):
            p.stop()

    def test_existing_job_returns_200(self) -> None:
        job = _make_job(id="job-1", status="completed", total_files=5, processed_files=5)
        with self._build_client_with_job(job) as c:
            resp = c.get("/api/v1/ingestion/status/job-1")
        app.dependency_overrides.clear()
        assert resp.status_code == 200

    def test_response_contains_all_fields(self) -> None:
        job = _make_job(
            id="job-1",
            status="running",
            total_files=10,
            processed_files=3,
            new_files=2,
            modified_files=1,
            deleted_files=0,
            skipped_files=0,
        )
        with self._build_client_with_job(job) as c:
            resp = c.get("/api/v1/ingestion/status/job-1")
        app.dependency_overrides.clear()
        body = resp.json()
        assert body["job_id"] == "job-1"
        assert body["status"] == "running"
        assert body["total_files"] == 10
        assert body["processed_files"] == 3
        assert body["new_files"] == 2
        assert body["modified_files"] == 1
        assert body["deleted_files"] == 0
        assert body["skipped_files"] == 0
        assert body["completed_at"] is None

    def test_completed_job_has_completed_at(self) -> None:
        job = _make_job(
            id="job-2",
            status="completed",
            completed_at=_NOW,
        )
        with self._build_client_with_job(job) as c:
            resp = c.get("/api/v1/ingestion/status/job-2")
        app.dependency_overrides.clear()
        assert resp.json()["completed_at"] is not None

    def test_missing_job_returns_404(self) -> None:
        with self._build_client_with_job(None) as c:
            resp = c.get("/api/v1/ingestion/status/ghost-job")
        app.dependency_overrides.clear()
        assert resp.status_code == 404

    def test_missing_job_error_code(self) -> None:
        with self._build_client_with_job(None) as c:
            resp = c.get("/api/v1/ingestion/status/ghost-job")
        app.dependency_overrides.clear()
        assert resp.json()["error"]["code"] == "ingestion_job_not_found"

    def test_request_id_header_present(self) -> None:
        job = _make_job(id="job-x")
        with self._build_client_with_job(job) as c:
            resp = c.get("/api/v1/ingestion/status/job-x")
        app.dependency_overrides.clear()
        assert "x-request-id" in resp.headers


# ---------------------------------------------------------------------------
# WS /api/v1/ingestion/progress/{job_id} — helper function tests
# ---------------------------------------------------------------------------


class TestIngestionWSHelpers:
    """Unit-test the pure helper functions in the ingestion module."""

    def test_normalize_progress_event(self) -> None:
        from app.api.routes.ingestion import _normalize_event

        raw = {
            "type": "progress",
            "job_id": "j1",
            "processed": 3,
            "total": 10,
            "current_file": "file.pdf",
        }
        out = _normalize_event(raw)
        assert out["processed_files"] == 3
        assert out["total_files"] == 10
        assert "processed" not in out
        assert "total" not in out
        assert out["current_file"] == "file.pdf"
        assert out["type"] == "progress"

    def test_normalize_file_complete_event(self) -> None:
        from app.api.routes.ingestion import _normalize_event

        raw = {
            "type": "file_complete",
            "job_id": "j1",
            "file_name": "doc.docx",
            "chunk_count": 15,
        }
        out = _normalize_event(raw)
        assert out["chunks_created"] == 15
        assert "chunk_count" not in out
        assert out["file_name"] == "doc.docx"

    def test_normalize_file_error_event_passthrough(self) -> None:
        from app.api.routes.ingestion import _normalize_event

        raw = {"type": "file_error", "job_id": "j1", "file_name": "bad.pdf", "error": "oops"}
        out = _normalize_event(raw)
        assert out["type"] == "file_error"
        assert out["error"] == "oops"

    def test_normalize_leaves_unknown_keys(self) -> None:
        from app.api.routes.ingestion import _normalize_event

        raw = {"type": "custom", "job_id": "j1", "some_extra": 42}
        out = _normalize_event(raw)
        assert out["some_extra"] == 42

    def test_terminal_event_completed(self) -> None:
        from app.api.routes.ingestion import _terminal_event_from_job

        job = _make_job(
            id="j1",
            status="completed",
            total_files=5,
            new_files=3,
            modified_files=1,
            deleted_files=0,
            skipped_files=1,
            completed_at=_NOW,
        )
        job.started_at = datetime(2026, 3, 4, 12, 0, 0, tzinfo=UTC)
        out = _terminal_event_from_job(job)
        assert out["type"] == "completed"
        assert out["job_id"] == "j1"
        assert out["total_files"] == 5
        assert out["new_files"] == 3
        assert out["modified_files"] == 1
        assert out["deleted_files"] == 0
        assert out["skipped_files"] == 1
        assert isinstance(out["duration_seconds"], float)

    def test_terminal_event_no_completed_at(self) -> None:
        from app.api.routes.ingestion import _terminal_event_from_job

        job = _make_job(id="j1", status="failed")
        out = _terminal_event_from_job(job)
        assert out["type"] == "failed"
        assert out["duration_seconds"] is None


# ---------------------------------------------------------------------------
# WS /api/v1/ingestion/progress/{job_id} — endpoint tests
# ---------------------------------------------------------------------------

_LIFESPAN_PATCHES = [
    "app.main.init_db",
    "app.main.init_singletons",
    "app.main.close_db",
    "app.main.get_singleton_vector_store",
    "app.main.get_singleton_embedding_provider",
    "app.main.get_singleton_llm_provider",
]


def _start_lifespan_patches() -> list:
    patches = [patch(target) for target in _LIFESPAN_PATCHES]
    patches.append(
        patch("app.services.model_manager.ModelManager.startup", new_callable=AsyncMock)
    )
    for p in patches:
        p.start()
    return patches


def _stop_patches(patches: list) -> None:
    for p in patches:
        p.stop()


def _make_ws_db_mock(job: IngestionJob | None) -> AsyncMock:
    """Build a mock AsyncSession whose execute() returns *job*."""
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = job
    db.execute = AsyncMock(return_value=result)
    return db


class TestIngestionProgressWS:
    """WebSocket progress endpoint tests."""

    def _ws_client(self, job: IngestionJob | None) -> tuple[TestClient, list]:
        """Return (TestClient, active_patches) with DB mocked to return *job*."""
        from contextlib import asynccontextmanager

        db_mock = _make_ws_db_mock(job)

        @asynccontextmanager
        async def _mock_get_session():
            yield db_mock

        patches = _start_lifespan_patches()
        gs_patch = patch("app.db.database.get_session", _mock_get_session)
        gs_patch.start()
        patches.append(gs_patch)
        return TestClient(app, raise_server_exceptions=False), patches

    # -- job not found -------------------------------------------------------

    def test_ws_not_found_sends_error(self) -> None:
        client, patches = self._ws_client(None)
        try:
            with client.websocket_connect("/api/v1/ingestion/progress/ghost") as ws:
                msg = ws.receive_json()
            assert msg["type"] == "error"
            assert msg["code"] == "not_found"
        finally:
            _stop_patches(patches)

    # -- already completed ---------------------------------------------------

    def test_ws_completed_job_sends_terminal_event(self) -> None:
        job = _make_job(id="j-done", status="completed", total_files=3, completed_at=_NOW)
        client, patches = self._ws_client(job)
        try:
            with client.websocket_connect("/api/v1/ingestion/progress/j-done") as ws:
                msg = ws.receive_json()
            assert msg["type"] == "completed"
            assert msg["job_id"] == "j-done"
            assert msg["total_files"] == 3
        finally:
            _stop_patches(patches)

    def test_ws_completed_job_duration_seconds_present(self) -> None:
        job = _make_job(id="j-done2", status="completed", completed_at=_NOW)
        client, patches = self._ws_client(job)
        try:
            with client.websocket_connect("/api/v1/ingestion/progress/j-done2") as ws:
                msg = ws.receive_json()
            assert "duration_seconds" in msg
        finally:
            _stop_patches(patches)

    # -- already failed ------------------------------------------------------

    def test_ws_failed_job_sends_terminal_event(self) -> None:
        job = _make_job(id="j-fail", status="failed")
        client, patches = self._ws_client(job)
        try:
            with client.websocket_connect("/api/v1/ingestion/progress/j-fail") as ws:
                msg = ws.receive_json()
            assert msg["type"] == "failed"
            assert msg["job_id"] == "j-fail"
        finally:
            _stop_patches(patches)

    # -- running job: live event streaming -----------------------------------

    def _make_fake_queue(self, events: list[dict]) -> object:
        """A fake asyncio.Queue whose get() yields pre-loaded events."""

        class _FakeQueue:
            def __init__(self) -> None:
                self._items = list(events)
                self._pos = 0

            async def get(self) -> dict:  # type: ignore[override]
                import asyncio

                if self._pos < len(self._items):
                    item = self._items[self._pos]
                    self._pos += 1
                    return item
                await asyncio.sleep(999)  # block indefinitely if exhausted
                return {}  # unreachable

        return _FakeQueue()

    def test_ws_running_job_relays_progress_event(self) -> None:
        import asyncio as _asyncio

        job = _make_job(id="j-run", status="running")
        client, patches = self._ws_client(job)
        fake_q = self._make_fake_queue([
            {"type": "progress", "job_id": "j-run", "processed": 1, "total": 5, "current_file": "a.pdf"},
            {"type": "_done_"},
        ])
        q_patch = patch.object(_asyncio, "Queue", return_value=fake_q)
        q_patch.start()
        patches.append(q_patch)
        try:
            with client.websocket_connect("/api/v1/ingestion/progress/j-run") as ws:
                msg = ws.receive_json()
            assert msg["type"] == "progress"
            assert msg["processed_files"] == 1
            assert msg["total_files"] == 5
            assert msg["current_file"] == "a.pdf"
        finally:
            _stop_patches(patches)

    def test_ws_running_job_relays_file_complete(self) -> None:
        import asyncio as _asyncio

        job = _make_job(id="j-run2", status="running")
        client, patches = self._ws_client(job)
        fake_q = self._make_fake_queue([
            {"type": "file_complete", "job_id": "j-run2", "file_name": "doc.pdf", "chunk_count": 7},
            {"type": "_done_"},
        ])
        q_patch = patch.object(_asyncio, "Queue", return_value=fake_q)
        q_patch.start()
        patches.append(q_patch)
        try:
            with client.websocket_connect("/api/v1/ingestion/progress/j-run2") as ws:
                msg = ws.receive_json()
            assert msg["type"] == "file_complete"
            assert msg["chunks_created"] == 7
            assert "chunk_count" not in msg
        finally:
            _stop_patches(patches)

    def test_ws_running_job_closes_after_completed_event(self) -> None:
        import asyncio as _asyncio

        job = _make_job(id="j-run3", status="running")
        client, patches = self._ws_client(job)
        fake_q = self._make_fake_queue([
            {"type": "progress", "job_id": "j-run3", "processed": 5, "total": 5, "current_file": "z.md"},
            {"type": "completed", "job_id": "j-run3", "processed": 5, "total": 5, "failed": 0},
        ])
        q_patch = patch.object(_asyncio, "Queue", return_value=fake_q)
        q_patch.start()
        patches.append(q_patch)
        try:
            messages = []
            with client.websocket_connect("/api/v1/ingestion/progress/j-run3") as ws:
                messages.append(ws.receive_json())  # progress
                messages.append(ws.receive_json())  # completed
            assert messages[0]["type"] == "progress"
            assert messages[1]["type"] == "completed"
        finally:
            _stop_patches(patches)
