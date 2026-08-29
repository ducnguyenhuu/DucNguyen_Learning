"""Integration tests for all REST API endpoints via FastAPI TestClient (T081).

Strategy
--------
- Import ``app`` from ``app.main`` but bypass the lifespan (no ModelManager
  startup, no Ollama, no sentence-transformers).
- Override all heavy singleton dependencies via ``app.dependency_overrides``.
- Use ``httpx.AsyncClient(transport=ASGITransport(app=app))`` for async HTTP.
- Share a single in-memory SQLite engine across the ``db`` fixture and the
  client's DB override so both see the same data.

Tests cover
-----------
- GET  /api/v1/health            — fallback response (§5.1)
- GET  /api/v1/config            — non-sensitive config (§5.2)
- POST /api/v1/conversations     — create (§2.1)
- GET  /api/v1/conversations     — list (§2.2)
- GET  /api/v1/conversations/:id — detail (§2.3)
- DELETE /api/v1/conversations/:id — single delete (§2.4)
- DELETE /api/v1/conversations?confirm=true — bulk clear (§2.5)
- POST /api/v1/conversations/:id/messages — chat send (§3.1)
- GET  /api/v1/documents         — list (§1.4)
- GET  /api/v1/documents/:id     — detail 404 (§1.5)
- DELETE /api/v1/documents/:id   — 404 path (§1.6)
- GET  /api/v1/ingestion/status/:id — 404 (§1.2)
- POST /api/v1/documents/:id/summary — generate (§4.1)
- GET  /api/v1/documents/:id/summary — cached / 404 (§4.2)
- Error response format (api-contracts.md §6)
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.deps import (
    get_db_session,
    get_embedding_provider,
    get_llm_provider,
    get_vector_store,
)
from app.db.database import Base
from app.db.vector_store import ChunkResult
from app.main import app
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.document_summary import DocumentSummary
from app.providers.base import EmbeddingProvider, LLMProvider

# ---------------------------------------------------------------------------
# Stub providers (no ML loading)
# ---------------------------------------------------------------------------


class _StubEmbeddingProvider(EmbeddingProvider):
    async def embed(self, text: str) -> list[float]:  # type: ignore[override]
        return [0.0] * 768

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:  # type: ignore[override]
        return [[0.0] * 768 for _ in texts]

    @property
    def model_version(self) -> str:
        return "stub-embed-v1"

    @property
    def dimensions(self) -> int:
        return 768

    async def _load_model(self) -> None:
        pass


class _StubLLM(LLMProvider):
    def __init__(self, response: str = "Test answer.") -> None:
        self._response = response

    async def generate(self, prompt: str, context: str = "") -> str:  # type: ignore[override]
        return self._response

    async def stream(self, prompt: str, context: str = "") -> AsyncIterator[str]:  # type: ignore[override]
        async def _gen() -> AsyncIterator[str]:
            yield self._response

        return _gen()

    @property
    def model_version(self) -> str:
        return "stub-llm-v0"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def test_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(test_engine):
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
async def db(session_factory):
    async with session_factory() as session:
        yield session


@pytest.fixture
def mock_vector_store() -> MagicMock:
    vs = MagicMock()
    vs.add_chunks = AsyncMock()
    vs.delete_by_document_id = AsyncMock()
    vs.query = AsyncMock(return_value=[])
    vs.get_chunks_by_document_id = AsyncMock(return_value=[])
    return vs


@pytest.fixture
async def api_client(session_factory, mock_vector_store):
    """Async HTTP client with all heavy dependencies replaced by stubs."""
    stub_llm = _StubLLM()
    stub_emb = _StubEmbeddingProvider()

    async def _override_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_vector_store] = lambda: mock_vector_store
    app.dependency_overrides[get_embedding_provider] = lambda: stub_emb
    app.dependency_overrides[get_llm_provider] = lambda: stub_llm

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_conversation(db: AsyncSession, title: str | None = None) -> Conversation:
    now = datetime.now(UTC)
    conv = Conversation(
        id=str(uuid.uuid4()),
        title=title,
        preview=None,
        message_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def _create_document(db: AsyncSession, status: str = "completed") -> Document:
    now = datetime.now(UTC)
    doc = Document(
        id=str(uuid.uuid4()),
        file_path=f"/docs/test_{uuid.uuid4()}.md",
        file_name="test.md",
        file_type="md",
        file_hash="aabbcc" + str(uuid.uuid4()).replace("-", "")[:10],
        file_size_bytes=1024,
        status=status,
        chunk_count=5,
        ingested_at=now,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


def _fake_chunk_result(document_id: str) -> ChunkResult:
    return ChunkResult(
        chunk_id=f"{document_id}_0",
        document_id=document_id,
        file_name="test.md",
        file_path="/docs/test.md",
        text="This is a test chunk with some content for summarization.",
        chunk_index=0,
        total_chunks=1,
        page_number=1,
        model_version="stub-embed-v1",
        distance=0.1,
    )


# ---------------------------------------------------------------------------
# System routes
# ---------------------------------------------------------------------------


class TestSystemRoutes:
    async def test_health_returns_200(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/api/v1/health")
        assert resp.status_code == 200

    async def test_health_contains_status_ok(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/api/v1/health")
        data = resp.json()
        assert data["status"] == "ok"

    async def test_config_returns_200(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/api/v1/config")
        assert resp.status_code == 200

    async def test_config_contains_expected_keys(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/api/v1/config")
        data = resp.json()
        for key in ("embedding_model", "llm_model", "chunk_size", "retrieval_top_k"):
            assert key in data, f"missing key: {key}"


# ---------------------------------------------------------------------------
# Conversation routes
# ---------------------------------------------------------------------------


class TestConversationRoutes:
    async def test_create_conversation_returns_201(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.post("/api/v1/conversations", json={})
        assert resp.status_code == 201

    async def test_create_conversation_has_id(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.post("/api/v1/conversations", json={})
        data = resp.json()
        assert "id" in data
        assert len(data["id"]) > 0

    async def test_create_conversation_with_title(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.post(
            "/api/v1/conversations", json={"title": "My Test Chat"}
        )
        assert resp.status_code == 201
        assert resp.json()["title"] == "My Test Chat"

    async def test_list_conversations_returns_200(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.get("/api/v1/conversations")
        assert resp.status_code == 200

    async def test_list_conversations_schema(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.get("/api/v1/conversations")
        data = resp.json()
        assert "conversations" in data
        assert "total" in data
        assert "page" in data

    async def test_get_conversation_detail_returns_200(
        self, api_client: AsyncClient, db: AsyncSession
    ) -> None:
        conv = await _create_conversation(db)
        resp = await api_client.get(f"/api/v1/conversations/{conv.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == conv.id

    async def test_get_conversation_detail_404_for_missing(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.get("/api/v1/conversations/nonexistent-id")
        assert resp.status_code == 404

    async def test_delete_conversation_returns_200(
        self, api_client: AsyncClient, db: AsyncSession
    ) -> None:
        conv = await _create_conversation(db)
        resp = await api_client.delete(f"/api/v1/conversations/{conv.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == conv.id

    async def test_delete_conversation_404_for_missing(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.delete("/api/v1/conversations/ghost-id")
        assert resp.status_code == 404

    async def test_bulk_clear_conversations(
        self, api_client: AsyncClient, db: AsyncSession
    ) -> None:
        # Create two conversations
        await _create_conversation(db)
        await _create_conversation(db)
        resp = await api_client.delete("/api/v1/conversations?confirm=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted_count"] >= 2

    async def test_bulk_clear_without_confirm_returns_400(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.delete("/api/v1/conversations")
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Chat routes
# ---------------------------------------------------------------------------


class TestChatRoutes:
    async def test_send_message_returns_200(
        self, api_client: AsyncClient, db: AsyncSession
    ) -> None:
        conv = await _create_conversation(db)
        resp = await api_client.post(
            f"/api/v1/conversations/{conv.id}/messages",
            json={"content": "What is the meaning of life?"},
        )
        assert resp.status_code == 200

    async def test_send_message_response_schema(
        self, api_client: AsyncClient, db: AsyncSession
    ) -> None:
        conv = await _create_conversation(db)
        resp = await api_client.post(
            f"/api/v1/conversations/{conv.id}/messages",
            json={"content": "Hello?"},
        )
        data = resp.json()
        assert "user_message" in data
        assert "assistant_message" in data
        assert data["user_message"]["content"] == "Hello?"
        assert data["user_message"]["role"] == "user"
        assert data["assistant_message"]["role"] == "assistant"

    async def test_send_message_404_for_unknown_conversation(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.post(
            "/api/v1/conversations/nonexistent-conv/messages",
            json={"content": "Hello?"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Document routes
# ---------------------------------------------------------------------------


class TestDocumentRoutes:
    async def test_list_documents_returns_200(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.get("/api/v1/documents")
        assert resp.status_code == 200

    async def test_list_documents_empty(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/api/v1/documents")
        data = resp.json()
        assert "documents" in data
        assert isinstance(data["documents"], list)

    async def test_get_document_detail_returns_200(
        self, api_client: AsyncClient, db: AsyncSession
    ) -> None:
        doc = await _create_document(db)
        resp = await api_client.get(f"/api/v1/documents/{doc.id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == doc.id

    async def test_get_document_detail_404_for_missing(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.get("/api/v1/documents/unknown-doc-id")
        assert resp.status_code == 404

    async def test_delete_document_returns_200(
        self, api_client: AsyncClient, db: AsyncSession
    ) -> None:
        doc = await _create_document(db)
        resp = await api_client.delete(f"/api/v1/documents/{doc.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == doc.id

    async def test_delete_document_404_for_missing(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.delete("/api/v1/documents/ghost-doc-id")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Ingestion routes
# ---------------------------------------------------------------------------


class TestIngestionRoutes:
    async def test_get_status_404_for_unknown_job(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.get(
            "/api/v1/ingestion/status/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404

    async def test_start_ingestion_invalid_path_returns_error(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.post(
            "/api/v1/ingestion/start",
            json={"source_folder": "/nonexistent/path/that/does/not/exist/at/all"},
        )
        # PathValidationError → 422
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Summary routes
# ---------------------------------------------------------------------------


class TestSummaryRoutes:
    async def test_generate_summary_returns_200(
        self,
        api_client: AsyncClient,
        db: AsyncSession,
        mock_vector_store: MagicMock,
    ) -> None:
        doc = await _create_document(db)
        mock_vector_store.get_chunks_by_document_id = AsyncMock(
            return_value=[_fake_chunk_result(doc.id)]
        )
        resp = await api_client.post(f"/api/v1/documents/{doc.id}/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == doc.id
        assert "summary_text" in data

    async def test_generate_summary_404_for_missing_document(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.post("/api/v1/documents/ghost-doc/summary")
        assert resp.status_code == 404

    async def test_generate_summary_409_for_pending_document(
        self, api_client: AsyncClient, db: AsyncSession
    ) -> None:
        doc = await _create_document(db, status="pending")
        resp = await api_client.post(f"/api/v1/documents/{doc.id}/summary")
        assert resp.status_code == 409

    async def test_get_summary_404_when_no_summary(
        self, api_client: AsyncClient, db: AsyncSession
    ) -> None:
        doc = await _create_document(db)
        resp = await api_client.get(f"/api/v1/documents/{doc.id}/summary")
        assert resp.status_code == 404

    async def test_get_summary_returns_cached_summary(
        self, api_client: AsyncClient, db: AsyncSession
    ) -> None:
        doc = await _create_document(db)
        # Create a summary directly in the DB
        summary = DocumentSummary(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            summary_text="Cached summary text.",
            section_references=None,
            model_version="stub-llm-v0",
            created_at=datetime.now(UTC),
        )
        db.add(summary)
        await db.commit()

        resp = await api_client.get(f"/api/v1/documents/{doc.id}/summary")
        assert resp.status_code == 200
        assert resp.json()["summary_text"] == "Cached summary text."


# ---------------------------------------------------------------------------
# Error response format (api-contracts.md §6)
# ---------------------------------------------------------------------------


class TestErrorResponseFormat:
    """Verify the structured error shape: {error: {code, message, request_id, details}}."""

    async def test_404_has_error_wrapper(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/api/v1/documents/does-not-exist")
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data
        err = data["error"]
        assert "code" in err
        assert "message" in err
        assert "request_id" in err

    async def test_404_conversation_message_has_error_wrapper(
        self, api_client: AsyncClient
    ) -> None:
        """POST .../messages for unknown conv raises ConversationNotFoundError (AppError)."""
        resp = await api_client.post(
            "/api/v1/conversations/does-not-exist/messages",
            json={"content": "hello"},
        )
        assert resp.status_code == 404
        err = resp.json()["error"]
        assert err["code"] == "conversation_not_found"

    async def test_404_document_has_correct_error_code(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.get("/api/v1/documents/no-such-doc")
        err = resp.json()["error"]
        assert err["code"] == "document_not_found"

    async def test_request_id_header_present(
        self, api_client: AsyncClient
    ) -> None:
        resp = await api_client.get("/api/v1/health")
        assert "x-request-id" in resp.headers
