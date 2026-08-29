"""Unit tests for document REST routes.

Tests HTTP contracts per api-contracts.md §1.4, §1.5, §1.6:
- GET    /api/v1/documents               → 200 (paginated list)
- GET    /api/v1/documents/{id}          → 200 / 404
- DELETE /api/v1/documents/{id}          → 200 / 404

All DB and vector store dependencies are replaced with lightweight mocks.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db_session, get_vector_store
from app.core.logging import configure_logging
from app.main import app
from app.models.document import Document
from app.models.document_summary import DocumentSummary

# Configure structlog once so lifespan log calls don't error.
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
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(
    *,
    id: str = "doc-1",
    file_name: str = "guide.pdf",
    file_type: str = "pdf",
    file_path: str = "/docs/guide.pdf",
    file_size_bytes: int = 1048576,
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_vs() -> MagicMock:
    vs = MagicMock()
    vs.delete_by_document_id = AsyncMock()
    return vs


@pytest.fixture
def client(mock_vs: MagicMock) -> TestClient:
    """TestClient with lifespan and injected vector store patched out."""
    patches = _start_lifespan_patches()

    app.dependency_overrides[get_vector_store] = lambda: mock_vs

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
    _stop_patches(patches)


def _make_db_for_docs(docs: list[Document], summary_count: int = 0) -> AsyncMock:
    """Build a mock AsyncSession that returns *docs* and a summary count."""
    db = AsyncMock()

    # Each execute() returns a result that can serve both list queries and
    # count queries.  We use call-count to distinguish the two calls in detail
    # and delete routes.
    call_count = {"n": 0}

    async def _execute(_stmt):
        call_count["n"] += 1
        result = MagicMock()
        result.scalars.return_value.all.return_value = docs
        result.scalars.return_value.first.return_value = docs[0] if docs else None
        result.scalar_one.return_value = summary_count if call_count["n"] > 1 else len(docs)
        return result

    db.execute = _execute
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    return db


def _client_with_db(db_mock: AsyncMock, mock_vs: MagicMock) -> tuple[TestClient, list]:
    async def _override_db() -> AsyncGenerator:
        yield db_mock

    patches = _start_lifespan_patches()
    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_vector_store] = lambda: mock_vs
    return TestClient(app, raise_server_exceptions=False), patches


# ---------------------------------------------------------------------------
# GET /api/v1/documents — list
# ---------------------------------------------------------------------------


class TestListDocuments:
    def test_returns_200(self, mock_vs: MagicMock) -> None:
        docs = [_make_doc(id="d1"), _make_doc(id="d2")]
        db = _make_db_for_docs(docs)
        client, patches = _client_with_db(db, mock_vs)
        try:
            with client as c:
                resp = c.get("/api/v1/documents")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_response_shape(self, mock_vs: MagicMock) -> None:
        docs = [_make_doc(id="d1"), _make_doc(id="d2")]
        db = _make_db_for_docs(docs)
        client, patches = _client_with_db(db, mock_vs)
        try:
            with client as c:
                body = c.get("/api/v1/documents").json()
            assert "documents" in body
            assert "total" in body
            assert "page" in body
            assert "page_size" in body
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_document_fields_present(self, mock_vs: MagicMock) -> None:
        docs = [_make_doc(id="d1", file_name="a.pdf", chunk_count=5)]
        db = _make_db_for_docs(docs)
        client, patches = _client_with_db(db, mock_vs)
        try:
            with client as c:
                body = c.get("/api/v1/documents").json()
            item = body["documents"][0]
            assert item["id"] == "d1"
            assert item["file_name"] == "a.pdf"
            assert item["chunk_count"] == 5
            assert item["status"] == "completed"
            assert item["file_type"] == "pdf"
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_pagination_params_forwarded(self, mock_vs: MagicMock) -> None:
        docs = [_make_doc()]
        db = _make_db_for_docs(docs)
        client, patches = _client_with_db(db, mock_vs)
        try:
            with client as c:
                body = c.get("/api/v1/documents?page=2&page_size=5").json()
            assert body["page"] == 2
            assert body["page_size"] == 5
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_empty_list(self, mock_vs: MagicMock) -> None:
        db = _make_db_for_docs([])
        client, patches = _client_with_db(db, mock_vs)
        try:
            with client as c:
                body = c.get("/api/v1/documents").json()
            assert body["documents"] == []
            assert body["total"] == 0
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_request_id_header(self, mock_vs: MagicMock) -> None:
        db = _make_db_for_docs([])
        client, patches = _client_with_db(db, mock_vs)
        try:
            with client as c:
                resp = c.get("/api/v1/documents")
            assert "x-request-id" in resp.headers
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)


# ---------------------------------------------------------------------------
# GET /api/v1/documents/{id} — detail
# ---------------------------------------------------------------------------


class TestGetDocument:
    def _client_with_doc(
        self, doc: Document | None, summary_count: int, mock_vs: MagicMock
    ) -> tuple[TestClient, list]:
        docs = [doc] if doc else []
        db = _make_db_for_docs(docs, summary_count=summary_count)
        return _client_with_db(db, mock_vs)

    def test_existing_doc_returns_200(self, mock_vs: MagicMock) -> None:
        doc = _make_doc(id="doc-x")
        client, patches = self._client_with_doc(doc, 0, mock_vs)
        try:
            with client as c:
                resp = c.get("/api/v1/documents/doc-x")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_response_has_all_fields(self, mock_vs: MagicMock) -> None:
        doc = _make_doc(id="doc-y", file_size_bytes=512000, chunk_count=10)
        client, patches = self._client_with_doc(doc, 0, mock_vs)
        try:
            with client as c:
                body = c.get("/api/v1/documents/doc-y").json()
            assert body["id"] == "doc-y"
            assert body["file_size_bytes"] == 512000
            assert body["chunk_count"] == 10
            assert "has_summary" in body
            assert "ingested_at" in body
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_has_summary_false_when_no_summary(self, mock_vs: MagicMock) -> None:
        doc = _make_doc(id="doc-ns")
        client, patches = self._client_with_doc(doc, 0, mock_vs)
        try:
            with client as c:
                body = c.get("/api/v1/documents/doc-ns").json()
            assert body["has_summary"] is False
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_has_summary_true_when_summary_exists(self, mock_vs: MagicMock) -> None:
        doc = _make_doc(id="doc-s")
        client, patches = self._client_with_doc(doc, 1, mock_vs)
        try:
            with client as c:
                body = c.get("/api/v1/documents/doc-s").json()
            assert body["has_summary"] is True
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_missing_doc_returns_404(self, mock_vs: MagicMock) -> None:
        client, patches = self._client_with_doc(None, 0, mock_vs)
        try:
            with client as c:
                resp = c.get("/api/v1/documents/ghost")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_missing_doc_error_code(self, mock_vs: MagicMock) -> None:
        client, patches = self._client_with_doc(None, 0, mock_vs)
        try:
            with client as c:
                body = c.get("/api/v1/documents/ghost").json()
            assert body["error"]["code"] == "document_not_found"
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_request_id_header(self, mock_vs: MagicMock) -> None:
        doc = _make_doc(id="doc-hdr")
        client, patches = self._client_with_doc(doc, 0, mock_vs)
        try:
            with client as c:
                resp = c.get("/api/v1/documents/doc-hdr")
            assert "x-request-id" in resp.headers
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)


# ---------------------------------------------------------------------------
# DELETE /api/v1/documents/{id}
# ---------------------------------------------------------------------------


class TestDeleteDocument:
    def _client_with_doc(
        self, doc: Document | None, mock_vs: MagicMock
    ) -> tuple[TestClient, list]:
        docs = [doc] if doc else []
        db = _make_db_for_docs(docs)
        return _client_with_db(db, mock_vs)

    def test_existing_doc_returns_200(self, mock_vs: MagicMock) -> None:
        doc = _make_doc(id="del-1")
        client, patches = self._client_with_doc(doc, mock_vs)
        try:
            with client as c:
                resp = c.delete("/api/v1/documents/del-1")
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_response_body_shape(self, mock_vs: MagicMock) -> None:
        doc = _make_doc(id="del-2", chunk_count=7)
        client, patches = self._client_with_doc(doc, mock_vs)
        try:
            with client as c:
                body = c.delete("/api/v1/documents/del-2").json()
            assert body["document_id"] == "del-2"
            assert "message" in body
            assert "7" in body["message"]
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_vector_store_delete_called(self, mock_vs: MagicMock) -> None:
        doc = _make_doc(id="del-3")
        client, patches = self._client_with_doc(doc, mock_vs)
        try:
            with client as c:
                c.delete("/api/v1/documents/del-3")
            mock_vs.delete_by_document_id.assert_awaited_once_with("del-3")
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_missing_doc_returns_404(self, mock_vs: MagicMock) -> None:
        client, patches = self._client_with_doc(None, mock_vs)
        try:
            with client as c:
                resp = c.delete("/api/v1/documents/ghost")
            assert resp.status_code == 404
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_missing_doc_error_code(self, mock_vs: MagicMock) -> None:
        client, patches = self._client_with_doc(None, mock_vs)
        try:
            with client as c:
                body = c.delete("/api/v1/documents/ghost").json()
            assert body["error"]["code"] == "document_not_found"
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)

    def test_request_id_header(self, mock_vs: MagicMock) -> None:
        doc = _make_doc(id="del-hdr")
        client, patches = self._client_with_doc(doc, mock_vs)
        try:
            with client as c:
                resp = c.delete("/api/v1/documents/del-hdr")
            assert "x-request-id" in resp.headers
        finally:
            app.dependency_overrides.clear()
            _stop_patches(patches)
