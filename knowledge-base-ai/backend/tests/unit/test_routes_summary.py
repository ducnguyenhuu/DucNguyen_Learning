"""Unit tests for document summary REST routes.

Tests HTTP contracts per api-contracts.md §4.1, §4.2:
- POST /api/v1/documents/{id}/summary  → 200 / 404 / 409 / 503
- GET  /api/v1/documents/{id}/summary  → 200 / 404

All DB and service dependencies are replaced with lightweight mocks.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db_session, get_vector_store
from app.core.exceptions import ModelUnavailableError
from app.core.logging import configure_logging
from app.main import app
from app.models.document import Document
from app.models.document_summary import DocumentSummary
from app.services.summary import SummaryGenerationError, SummaryService

configure_logging(level="WARNING", fmt="console")

_NOW = datetime(2026, 3, 5, 12, 0, 0, tzinfo=UTC)

_LIFESPAN_PATCHES = [
    "app.main.init_db",
    "app.main.init_singletons",
    "app.main.close_db",
    "app.main.get_singleton_vector_store",
    "app.main.get_singleton_embedding_provider",
    "app.main.get_singleton_llm_provider",
]


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _make_doc(
    *,
    id: str = "doc-1",
    file_name: str = "guide.pdf",
    file_type: str = "pdf",
    file_path: str = "/docs/guide.pdf",
    file_size_bytes: int = 1_048_576,
    chunk_count: int = 42,
    status: str = "completed",
    ingested_at: datetime | None = _NOW,
) -> Document:
    doc = Document(
        id=id,
        file_name=file_name,
        file_type=file_type,
        file_path=file_path,
        file_hash="abc123",
        file_size_bytes=file_size_bytes,
        chunk_count=chunk_count,
        status=status,
    )
    doc.ingested_at = ingested_at
    return doc


def _make_summary(
    *,
    id: str = "sum-1",
    document_id: str = "doc-1",
    summary_text: str = "This is a test summary.",
    section_references: list | None = None,
    model_version: str = "phi3.5",
    created_at: datetime = _NOW,
) -> DocumentSummary:
    s = DocumentSummary(
        id=id,
        document_id=document_id,
        summary_text=summary_text,
        section_references=section_references,
        model_version=model_version,
    )
    s.created_at = created_at
    return s


# ---------------------------------------------------------------------------
# Infrastructure helpers
# ---------------------------------------------------------------------------


def _start_lifespan_patches() -> list:
    patches = [patch(t) for t in _LIFESPAN_PATCHES]
    patches.append(
        patch("app.services.model_manager.ModelManager.startup", new_callable=AsyncMock)
    )
    for p in patches:
        p.start()
    return patches


def _stop_patches(patches: list) -> None:
    for p in patches:
        p.stop()


def _make_db(doc: Document | None, summary: DocumentSummary | None = None) -> AsyncMock:
    """Build a mock AsyncSession that returns *doc* from a scalars().first() call."""
    scalar_result_doc = MagicMock()
    scalar_result_doc.scalars.return_value.first.return_value = doc

    scalar_result_summary = MagicMock()
    scalar_result_summary.scalars.return_value.first.return_value = summary

    db = AsyncMock()
    # First execute → document lookup; second execute → summary lookup
    db.execute = AsyncMock(
        side_effect=[scalar_result_doc, scalar_result_summary]
    )
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda obj: None)
    return db


def _mock_summary_svc_get_or_generate(summary: DocumentSummary) -> MagicMock:
    svc = MagicMock(spec=SummaryService)
    svc.get_or_generate = AsyncMock(return_value=summary)
    svc.get_cached = AsyncMock(return_value=summary)
    return svc


def _client_with_db(
    db_mock: AsyncMock,
    mock_vs: MagicMock,
    summary_svc_mock: MagicMock | None = None,
) -> tuple[TestClient, list]:
    patches = _start_lifespan_patches()

    async def _override_db() -> AsyncGenerator:
        yield db_mock

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_vector_store] = lambda: mock_vs

    if summary_svc_mock is not None:
        from app.api.deps import get_summary_service
        app.dependency_overrides[get_summary_service] = lambda: summary_svc_mock

    return TestClient(app, raise_server_exceptions=False), patches


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_vs() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# POST /api/v1/documents/{id}/summary
# ---------------------------------------------------------------------------


class TestGenerateSummary:
    def test_returns_200_on_success(self, mock_vs: MagicMock) -> None:
        doc = _make_doc()
        summary = _make_summary()
        db = _make_db(doc, summary)
        svc = _mock_summary_svc_get_or_generate(summary)
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                resp = c.post("/api/v1/documents/doc-1/summary")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_response_shape(self, mock_vs: MagicMock) -> None:
        doc = _make_doc()
        summary = _make_summary(
            section_references=[
                {"section": "Page 1", "page": 1, "contribution": "Introduction"}
            ]
        )
        db = _make_db(doc, summary)
        svc = _mock_summary_svc_get_or_generate(summary)
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                body = c.post("/api/v1/documents/doc-1/summary").json()
            assert body["id"] == "sum-1"
            assert body["document_id"] == "doc-1"
            assert body["summary_text"] == "This is a test summary."
            assert body["model_version"] == "phi3.5"
            assert body["section_references"][0]["section"] == "Page 1"
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_returns_404_when_document_missing(self, mock_vs: MagicMock) -> None:
        db = _make_db(None)
        svc = _mock_summary_svc_get_or_generate(_make_summary())
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                resp = c.post("/api/v1/documents/ghost/summary")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_404_error_code(self, mock_vs: MagicMock) -> None:
        db = _make_db(None)
        svc = _mock_summary_svc_get_or_generate(_make_summary())
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                body = c.post("/api/v1/documents/ghost/summary").json()
            assert body["error"]["code"] == "document_not_found"
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_returns_409_when_document_not_completed(self, mock_vs: MagicMock) -> None:
        doc = _make_doc(status="processing")
        db = _make_db(doc)
        svc = _mock_summary_svc_get_or_generate(_make_summary())
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                resp = c.post("/api/v1/documents/doc-1/summary")
            assert resp.status_code == 409
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_409_error_code(self, mock_vs: MagicMock) -> None:
        doc = _make_doc(status="pending")
        db = _make_db(doc)
        svc = _mock_summary_svc_get_or_generate(_make_summary())
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                body = c.post("/api/v1/documents/doc-1/summary").json()
            assert body["error"]["code"] == "document_not_ready"
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_returns_503_when_no_chunks(self, mock_vs: MagicMock) -> None:
        doc = _make_doc()
        db = _make_db(doc)
        svc = MagicMock(spec=SummaryService)
        svc.get_or_generate = AsyncMock(
            side_effect=SummaryGenerationError(
                document_id="doc-1", reason="No chunks found"
            )
        )
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                resp = c.post("/api/v1/documents/doc-1/summary")
            assert resp.status_code == 503
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_503_error_code(self, mock_vs: MagicMock) -> None:
        doc = _make_doc()
        db = _make_db(doc)
        svc = MagicMock(spec=SummaryService)
        svc.get_or_generate = AsyncMock(
            side_effect=SummaryGenerationError(
                document_id="doc-1", reason="No chunks found"
            )
        )
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                body = c.post("/api/v1/documents/doc-1/summary").json()
            assert body["error"]["code"] == "model_unavailable"
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)


# ---------------------------------------------------------------------------
# GET /api/v1/documents/{id}/summary
# ---------------------------------------------------------------------------


class TestGetSummary:
    def test_returns_200_when_summary_exists(self, mock_vs: MagicMock) -> None:
        doc = _make_doc()
        summary = _make_summary()
        db = _make_db(doc, summary)
        svc = _mock_summary_svc_get_or_generate(summary)
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                resp = c.get("/api/v1/documents/doc-1/summary")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_response_contains_summary_text(self, mock_vs: MagicMock) -> None:
        doc = _make_doc()
        summary = _make_summary(summary_text="Detailed system summary.")
        db = _make_db(doc, summary)
        svc = _mock_summary_svc_get_or_generate(summary)
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                body = c.get("/api/v1/documents/doc-1/summary").json()
            assert body["summary_text"] == "Detailed system summary."
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_returns_404_when_document_missing(self, mock_vs: MagicMock) -> None:
        db = _make_db(None)
        svc = MagicMock(spec=SummaryService)
        svc.get_cached = AsyncMock(return_value=None)
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                resp = c.get("/api/v1/documents/ghost/summary")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_returns_404_when_summary_missing(self, mock_vs: MagicMock) -> None:
        doc = _make_doc()
        db = _make_db(doc, None)
        svc = MagicMock(spec=SummaryService)
        svc.get_cached = AsyncMock(return_value=None)
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                resp = c.get("/api/v1/documents/doc-1/summary")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_404_error_code_for_missing_summary(self, mock_vs: MagicMock) -> None:
        doc = _make_doc()
        db = _make_db(doc, None)
        svc = MagicMock(spec=SummaryService)
        svc.get_cached = AsyncMock(return_value=None)
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                body = c.get("/api/v1/documents/doc-1/summary").json()
            assert body["error"]["code"] == "summary_not_found"
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_section_references_in_response(self, mock_vs: MagicMock) -> None:
        doc = _make_doc()
        summary = _make_summary(
            section_references=[
                {"section": "Page 1", "page": 1, "contribution": "Overview"},
                {"section": "Page 5", "page": 5, "contribution": "Details"},
            ]
        )
        db = _make_db(doc, summary)
        svc = _mock_summary_svc_get_or_generate(summary)
        client, patches = _client_with_db(db, mock_vs, svc)
        try:
            with client as c:
                body = c.get("/api/v1/documents/doc-1/summary").json()
            refs = body["section_references"]
            assert len(refs) == 2
            assert refs[0]["section"] == "Page 1"
            assert refs[0]["page"] == 1
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)
