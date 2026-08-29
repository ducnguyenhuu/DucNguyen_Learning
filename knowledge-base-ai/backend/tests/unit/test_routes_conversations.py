"""Unit tests for conversation REST routes.

Tests HTTP contracts per api-contracts.md §2.1–§2.5:
  POST   /api/v1/conversations               — create new conversation
  GET    /api/v1/conversations               — paginated list
  GET    /api/v1/conversations/{id}          — full message history
  DELETE /api/v1/conversations/{id}          — single cascade delete
  DELETE /api/v1/conversations?confirm=true  — bulk clear

All DB dependencies are replaced with lightweight mocks.
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_db_session
from app.core.logging import configure_logging
from app.main import app
from app.models.conversation import Conversation
from app.models.message import Message

# Configure structlog once so lifespan log calls don't error.
configure_logging(level="WARNING", fmt="console")

_NOW = datetime(2026, 3, 5, 12, 0, 0, tzinfo=UTC)
_CONV_ID = "aaaaaaaa-0000-0000-0000-000000000001"

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


def _make_conv(
    *,
    id: str = _CONV_ID,
    title: str | None = None,
    message_count: int = 0,
) -> Conversation:
    """Build a Conversation ORM instance for testing."""
    conv = MagicMock(spec=Conversation)
    conv.id = id
    conv.title = title
    conv.preview = None
    conv.message_count = message_count
    conv.created_at = _NOW
    conv.updated_at = _NOW
    return conv


def _make_db(conv: Conversation) -> AsyncMock:
    """Build a mock AsyncSession that captures add() and handles commit/refresh."""
    db = AsyncMock()
    db.add = MagicMock()

    # refresh() sets the id/created_at on the conv from what we already have
    async def _refresh(obj: object) -> None:
        pass  # conv already has all fields set

    db.refresh.side_effect = _refresh
    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    """TestClient with lifespan patched out."""
    patches = _start_lifespan_patches()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()
    _stop_patches(patches)


# ---------------------------------------------------------------------------
# POST /api/v1/conversations  (§2.1)
# ---------------------------------------------------------------------------


class TestCreateConversation:
    """POST /api/v1/conversations"""

    def test_returns_201_no_body(self, client: TestClient) -> None:
        """Sending no body creates a conversation with null title."""
        captured: list[Conversation] = []

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.add = MagicMock(side_effect=lambda obj: captured.append(obj))
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen

        resp = client.post("/api/v1/conversations")

        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] is None
        assert body["preview"] is None
        assert body["message_count"] == 0
        assert "id" in body
        assert "created_at" in body

    def test_returns_201_with_title(self, client: TestClient) -> None:
        """Providing a title stores it on the conversation."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.add = MagicMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen

        resp = client.post(
            "/api/v1/conversations",
            json={"title": "My chat"},
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "My chat"
        assert body["message_count"] == 0

    def test_returns_201_empty_json_body(self, client: TestClient) -> None:
        """Sending an empty JSON object creates a conversation with null title."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.add = MagicMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen

        resp = client.post("/api/v1/conversations", json={})

        assert resp.status_code == 201
        assert resp.json()["title"] is None

    def test_response_schema(self, client: TestClient) -> None:
        """Response contains all required fields per §2.1."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.add = MagicMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen

        resp = client.post("/api/v1/conversations", json={"title": "Test"})
        assert resp.status_code == 201
        body = resp.json()
        assert set(body.keys()) == {"id", "title", "preview", "message_count", "created_at"}

    def test_id_is_uuid_format(self, client: TestClient) -> None:
        """The returned id must be a UUID string."""
        import re

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.add = MagicMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen

        resp = client.post("/api/v1/conversations")
        assert resp.status_code == 201
        conv_id = resp.json()["id"]
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            conv_id,
        ), f"Expected UUID, got {conv_id!r}"

    def test_db_add_and_commit_called(self, client: TestClient) -> None:
        """Verify that db.add() and db.commit() are called during creation."""
        add_calls: list = []
        commit_calls: list = []

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.add = MagicMock(side_effect=lambda obj: add_calls.append(obj))
            db.commit = AsyncMock(side_effect=lambda: commit_calls.append(True))
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen

        resp = client.post("/api/v1/conversations")
        assert resp.status_code == 201
        assert len(add_calls) == 1, "db.add() should be called once"
        assert len(commit_calls) == 1, "db.commit() should be called once"
        assert isinstance(add_calls[0], Conversation)

    def test_conversation_has_zero_message_count(self, client: TestClient) -> None:
        """Newly created conversation always has message_count = 0."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.add = MagicMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen

        resp = client.post("/api/v1/conversations")
        assert resp.status_code == 201
        assert resp.json()["message_count"] == 0

    def test_null_title_when_not_provided(self, client: TestClient) -> None:
        """Title is null in the response when not set."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.add = MagicMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen

        resp = client.post("/api/v1/conversations")
        assert resp.json()["title"] is None

    def test_null_preview_on_creation(self, client: TestClient) -> None:
        """Preview is always null on initial creation."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.add = MagicMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen

        resp = client.post("/api/v1/conversations", json={"title": "Anything"})
        assert resp.json()["preview"] is None

    def test_x_request_id_header_present(self, client: TestClient) -> None:
        """X-Request-ID header must be present in the response."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.add = MagicMock()
            db.refresh = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen

        resp = client.post("/api/v1/conversations")
        assert "x-request-id" in resp.headers or "X-Request-ID" in resp.headers


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

_MSG_ID = "bbbbbbbb-0000-0000-0000-000000000002"
_CONV_ID_2 = "aaaaaaaa-0000-0000-0000-000000000002"


def _make_message(
    *,
    id: str = _MSG_ID,
    conversation_id: str = _CONV_ID,
    role: str = "user",
    content: str = "Hello",
    source_references: list | None = None,
) -> Message:
    msg = MagicMock(spec=Message)
    msg.id = id
    msg.conversation_id = conversation_id
    msg.role = role
    msg.content = content
    msg.source_references = source_references
    msg.token_count = None
    msg.created_at = _NOW
    return msg


def _execute_side_effects(*results: MagicMock) -> list[MagicMock]:
    """Return a list of AsyncMock-compatible mock results for db.execute()."""
    return list(results)


def _count_result(n: int) -> MagicMock:
    r = MagicMock()
    r.scalar_one.return_value = n
    return r


def _rows_result(items: list) -> MagicMock:
    r = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = items
    r.scalars.return_value = scalars
    return r


def _scalar_one_or_none_result(obj: object | None) -> MagicMock:
    r = MagicMock()
    r.scalar_one_or_none.return_value = obj
    return r


# ---------------------------------------------------------------------------
# GET /api/v1/conversations  (§2.2)
# ---------------------------------------------------------------------------


class TestListConversations:
    """GET /api/v1/conversations"""

    def test_returns_200_empty_list(self, client: TestClient) -> None:
        """Empty database returns 200 with empty conversations list."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_count_result(0), _rows_result([])]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        resp = client.get("/api/v1/conversations")

        assert resp.status_code == 200
        body = resp.json()
        assert body["conversations"] == []
        assert body["total"] == 0

    def test_response_schema(self, client: TestClient) -> None:
        """Response has conversations, total, page, page_size fields."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_count_result(0), _rows_result([])]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        body = client.get("/api/v1/conversations").json()

        assert set(body.keys()) == {"conversations", "total", "page", "page_size"}

    def test_returns_conversations_with_required_fields(self, client: TestClient) -> None:
        """Each item includes id, title, preview, message_count, created_at, updated_at."""
        conv = _make_conv(title="My Chat", message_count=3)

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_count_result(1), _rows_result([conv])]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        body = client.get("/api/v1/conversations").json()

        assert len(body["conversations"]) == 1
        item = body["conversations"][0]
        assert set(item.keys()) == {"id", "title", "preview", "message_count", "created_at", "updated_at"}
        assert item["title"] == "My Chat"
        assert item["message_count"] == 3

    def test_total_reflects_count(self, client: TestClient) -> None:
        """total field matches the DB count."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_count_result(42), _rows_result([])]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        body = client.get("/api/v1/conversations").json()

        assert body["total"] == 42

    def test_default_pagination(self, client: TestClient) -> None:
        """Without params, page=1 and page_size=20 are returned."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_count_result(0), _rows_result([])]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        body = client.get("/api/v1/conversations").json()

        assert body["page"] == 1
        assert body["page_size"] == 20

    def test_custom_pagination_params(self, client: TestClient) -> None:
        """page and page_size query params are reflected in the response."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_count_result(100), _rows_result([])]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        body = client.get("/api/v1/conversations?page=3&page_size=5").json()

        assert body["page"] == 3
        assert body["page_size"] == 5

    def test_x_request_id_header(self, client: TestClient) -> None:
        """Response must carry X-Request-ID header."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_count_result(0), _rows_result([])]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        resp = client.get("/api/v1/conversations")

        assert "x-request-id" in resp.headers or "X-Request-ID" in resp.headers


# ---------------------------------------------------------------------------
# GET /api/v1/conversations/{conversation_id}  (§2.3)
# ---------------------------------------------------------------------------


class TestGetConversation:
    """GET /api/v1/conversations/{conversation_id}"""

    def test_returns_200_with_messages(self, client: TestClient) -> None:
        """Returns 200 with message history for existing conversation."""
        conv = _make_conv(title="Tech chat")
        msg = _make_message(role="user", content="What is CQRS?")

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_scalar_one_or_none_result(conv), _rows_result([msg])]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        resp = client.get(f"/api/v1/conversations/{_CONV_ID}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == _CONV_ID
        assert body["title"] == "Tech chat"
        assert len(body["messages"]) == 1
        assert body["messages"][0]["content"] == "What is CQRS?"

    def test_response_schema(self, client: TestClient) -> None:
        """Response has id, title, messages, created_at, updated_at."""
        conv = _make_conv()

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_scalar_one_or_none_result(conv), _rows_result([])]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        body = client.get(f"/api/v1/conversations/{_CONV_ID}").json()

        assert set(body.keys()) == {"id", "title", "messages", "created_at", "updated_at"}

    def test_message_schema(self, client: TestClient) -> None:
        """Each message has id, role, content, source_references, created_at."""
        conv = _make_conv()
        msg = _make_message(role="assistant", content="Answer...", source_references=None)

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_scalar_one_or_none_result(conv), _rows_result([msg])]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        body = client.get(f"/api/v1/conversations/{_CONV_ID}").json()

        m = body["messages"][0]
        assert set(m.keys()) == {"id", "role", "content", "source_references", "created_at"}
        assert m["role"] == "assistant"

    def test_source_references_included(self, client: TestClient) -> None:
        """source_references array is serialised when present."""
        conv = _make_conv()
        refs = [{"document_id": "doc-1", "file_name": "guide.pdf", "page_number": 5, "relevance_score": 0.9}]
        msg = _make_message(role="assistant", source_references=refs)

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_scalar_one_or_none_result(conv), _rows_result([msg])]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        body = client.get(f"/api/v1/conversations/{_CONV_ID}").json()

        assert body["messages"][0]["source_references"] == refs

    def test_returns_empty_messages_list(self, client: TestClient) -> None:
        """Returns empty messages list for conversation with no messages."""
        conv = _make_conv()

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_scalar_one_or_none_result(conv), _rows_result([])]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        body = client.get(f"/api/v1/conversations/{_CONV_ID}").json()

        assert body["messages"] == []

    def test_returns_404_when_not_found(self, client: TestClient) -> None:
        """Returns 404 if conversation_id does not exist."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                return_value=_scalar_one_or_none_result(None)
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        resp = client.get("/api/v1/conversations/does-not-exist")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/conversations/{conversation_id}  (§2.4)
# ---------------------------------------------------------------------------


class TestDeleteConversation:
    """DELETE /api/v1/conversations/{conversation_id}"""

    def test_returns_200_on_success(self, client: TestClient) -> None:
        """Returns 200 with message and conversation_id."""
        conv = _make_conv()

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(return_value=_scalar_one_or_none_result(conv))
            db.delete = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        resp = client.delete(f"/api/v1/conversations/{_CONV_ID}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["conversation_id"] == _CONV_ID
        assert "deleted" in body["message"].lower()

    def test_response_schema(self, client: TestClient) -> None:
        """Response has exactly message and conversation_id."""
        conv = _make_conv()

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(return_value=_scalar_one_or_none_result(conv))
            db.delete = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        body = client.delete(f"/api/v1/conversations/{_CONV_ID}").json()

        assert set(body.keys()) == {"message", "conversation_id"}

    def test_returns_404_when_not_found(self, client: TestClient) -> None:
        """Returns 404 if conversation_id does not exist."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(return_value=_scalar_one_or_none_result(None))
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        resp = client.delete("/api/v1/conversations/no-such-id")

        assert resp.status_code == 404

    def test_db_delete_and_commit_called(self, client: TestClient) -> None:
        """Verify db.delete() and db.commit() are called."""
        conv = _make_conv()
        delete_calls: list = []
        commit_calls: list = []

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(return_value=_scalar_one_or_none_result(conv))
            db.delete = AsyncMock(side_effect=lambda obj: delete_calls.append(obj))
            db.commit = AsyncMock(side_effect=lambda: commit_calls.append(True))
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        client.delete(f"/api/v1/conversations/{_CONV_ID}")

        assert len(delete_calls) == 1
        assert len(commit_calls) == 1

    def test_conversation_id_in_url_reflected_in_response(self, client: TestClient) -> None:
        """conversation_id in the response matches the URL path param."""
        conv = _make_conv(id=_CONV_ID_2)

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(return_value=_scalar_one_or_none_result(conv))
            db.delete = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        body = client.delete(f"/api/v1/conversations/{_CONV_ID_2}").json()

        assert body["conversation_id"] == _CONV_ID_2


# ---------------------------------------------------------------------------
# DELETE /api/v1/conversations?confirm=true  (§2.5 / FR-024)
# ---------------------------------------------------------------------------


class TestClearConversations:
    """DELETE /api/v1/conversations — bulk clear"""

    def test_returns_200_with_confirm_true(self, client: TestClient) -> None:
        """Returns 200 with deleted_count when confirm=true."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_count_result(5), MagicMock()]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        resp = client.delete("/api/v1/conversations?confirm=true")

        assert resp.status_code == 200
        body = resp.json()
        assert body["deleted_count"] == 5
        assert "deleted" in body["message"].lower()

    def test_response_schema(self, client: TestClient) -> None:
        """Response has exactly message and deleted_count."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_count_result(0), MagicMock()]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        body = client.delete("/api/v1/conversations?confirm=true").json()

        assert set(body.keys()) == {"message", "deleted_count"}

    def test_returns_400_when_confirm_missing(self, client: TestClient) -> None:
        """Returns 400 when confirm param is absent (FR-024)."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        resp = client.delete("/api/v1/conversations")

        assert resp.status_code == 400

    def test_returns_400_when_confirm_false(self, client: TestClient) -> None:
        """Returns 400 when confirm=false (FR-024)."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        resp = client.delete("/api/v1/conversations?confirm=false")

        assert resp.status_code == 400

    def test_deleted_count_is_zero_for_empty_db(self, client: TestClient) -> None:
        """deleted_count is 0 when there are no conversations."""
        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()
            db.execute = AsyncMock(
                side_effect=[_count_result(0), MagicMock()]
            )
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        body = client.delete("/api/v1/conversations?confirm=true").json()

        assert body["deleted_count"] == 0

    def test_execute_and_commit_called(self, client: TestClient) -> None:
        """db.execute() is called twice (count + delete) and commit once."""
        execute_calls: list = []
        commit_calls: list = []

        async def _db_gen():  # type: ignore[override]
            db = AsyncMock()

            async def _execute(stmt):  # type: ignore[override]
                execute_calls.append(stmt)
                if len(execute_calls) == 1:
                    return _count_result(3)
                return MagicMock()

            db.execute = _execute
            db.commit = AsyncMock(side_effect=lambda: commit_calls.append(True))
            yield db

        app.dependency_overrides[get_db_session] = _db_gen
        client.delete("/api/v1/conversations?confirm=true")

        assert len(execute_calls) == 2
        assert len(commit_calls) == 1
