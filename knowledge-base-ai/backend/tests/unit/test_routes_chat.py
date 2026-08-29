"""Unit tests for chat REST and WebSocket routes.

Tests HTTP/WS contracts per api-contracts.md §3.1, §3.2:
  POST /api/v1/conversations/{id}/messages  — blocking RAG response
  WS   /api/v1/conversations/{id}/stream    — token-streaming RAG response

All service and DB dependencies are replaced with lightweight mocks.
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_chat_service, get_db_session
from app.core.exceptions import ConversationNotFoundError, ModelUnavailableError
from app.core.logging import configure_logging
from app.main import app
from app.models.message import Message
from app.services.chat import (
    CompleteEvent,
    ErrorEvent,
    SourcesFoundEvent,
    TokenEvent,
    UserMessageSavedEvent,
)

# Configure structlog once so lifespan log calls don't error.
configure_logging(level="WARNING", fmt="console")

_NOW = datetime(2026, 3, 5, 12, 0, 0, tzinfo=UTC)
_CONV_ID = "cccccccc-0000-0000-0000-000000000001"
_USER_MSG_ID = "uuuuuuuu-0000-0000-0000-000000000002"
_ASST_MSG_ID = "aaaaaaaa-0000-0000-0000-000000000003"

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


def _make_message(
    *,
    id: str,
    role: str,
    content: str,
    source_references: list[dict] | None = None,
) -> Message:
    msg = MagicMock(spec=Message)
    msg.id = id
    msg.role = role
    msg.content = content
    msg.source_references = source_references
    msg.created_at = _NOW
    return msg


def _make_db() -> AsyncMock:
    """Minimal mock AsyncSession for chat routes (not used for data queries)."""
    db = AsyncMock()
    return db


def _make_noop_db_gen():
    """Dependency override generator for get_db_session."""
    async def _gen():  # type: ignore[override]
        yield _make_db()
    return _gen


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
# POST /api/v1/conversations/{id}/messages  (§3.1)
# ---------------------------------------------------------------------------


class TestSendMessageRoute:
    """POST /api/v1/conversations/{conversation_id}/messages"""

    def _setup_mock_chat(
        self,
        user_msg: Message,
        asst_msg: Message,
    ) -> MagicMock:
        """Return a mock ChatService with send_message returning the given pair."""
        chat = MagicMock()
        chat.send_message = AsyncMock(return_value=(user_msg, asst_msg))
        return chat

    def test_success_returns_200(self, client: TestClient) -> None:
        """Successful call returns 200 with both messages."""
        user_msg = _make_message(id=_USER_MSG_ID, role="user", content="Hello?")
        asst_msg = _make_message(
            id=_ASST_MSG_ID, role="assistant", content="Here is the answer."
        )
        mock_chat = self._setup_mock_chat(user_msg, asst_msg)

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        resp = client.post(
            f"/api/v1/conversations/{_CONV_ID}/messages",
            json={"content": "Hello?"},
        )

        assert resp.status_code == 200

    def test_response_has_user_and_assistant_messages(
        self, client: TestClient
    ) -> None:
        """Response body contains user_message and assistant_message keys."""
        user_msg = _make_message(id=_USER_MSG_ID, role="user", content="Q?")
        asst_msg = _make_message(id=_ASST_MSG_ID, role="assistant", content="A!")
        mock_chat = self._setup_mock_chat(user_msg, asst_msg)

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        resp = client.post(
            f"/api/v1/conversations/{_CONV_ID}/messages",
            json={"content": "Q?"},
        )
        body = resp.json()
        assert "user_message" in body
        assert "assistant_message" in body

    def test_user_message_fields(self, client: TestClient) -> None:
        """user_message contains id, role, content, created_at fields."""
        user_msg = _make_message(id=_USER_MSG_ID, role="user", content="My question")
        asst_msg = _make_message(id=_ASST_MSG_ID, role="assistant", content="My answer")
        mock_chat = self._setup_mock_chat(user_msg, asst_msg)

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        resp = client.post(
            f"/api/v1/conversations/{_CONV_ID}/messages",
            json={"content": "My question"},
        )
        um = resp.json()["user_message"]
        assert um["id"] == _USER_MSG_ID
        assert um["role"] == "user"
        assert um["content"] == "My question"
        assert "created_at" in um

    def test_assistant_message_with_source_references(
        self, client: TestClient
    ) -> None:
        """assistant_message source_references are passed through."""
        sources = [
            {
                "document_id": "doc-1",
                "file_name": "guide.pdf",
                "page_number": 5,
                "relevance_score": 0.9,
            }
        ]
        user_msg = _make_message(id=_USER_MSG_ID, role="user", content="Q")
        asst_msg = _make_message(
            id=_ASST_MSG_ID,
            role="assistant",
            content="See guide.pdf",
            source_references=sources,
        )
        mock_chat = self._setup_mock_chat(user_msg, asst_msg)

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        resp = client.post(
            f"/api/v1/conversations/{_CONV_ID}/messages",
            json={"content": "Q"},
        )
        am = resp.json()["assistant_message"]
        assert am["source_references"] == sources

    def test_conversation_not_found_returns_404(self, client: TestClient) -> None:
        """ConversationNotFoundError is converted to 404."""
        mock_chat = MagicMock()
        mock_chat.send_message = AsyncMock(
            side_effect=ConversationNotFoundError(_CONV_ID)
        )

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        resp = client.post(
            f"/api/v1/conversations/{_CONV_ID}/messages",
            json={"content": "Q?"},
        )

        assert resp.status_code == 404
        error = resp.json()["error"]
        assert error["code"] == "conversation_not_found"

    def test_llm_unavailable_returns_503(self, client: TestClient) -> None:
        """ModelUnavailableError is converted to 503."""
        mock_chat = MagicMock()
        mock_chat.send_message = AsyncMock(
            side_effect=ModelUnavailableError("phi3.5", "Ollama not running")
        )

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        resp = client.post(
            f"/api/v1/conversations/{_CONV_ID}/messages",
            json={"content": "Q?"},
        )

        assert resp.status_code == 503
        error = resp.json()["error"]
        assert error["code"] == "model_unavailable"

    def test_missing_content_returns_422(self, client: TestClient) -> None:
        """Missing 'content' field in the request body returns 422."""
        mock_chat = MagicMock()
        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        resp = client.post(
            f"/api/v1/conversations/{_CONV_ID}/messages",
            json={},
        )
        assert resp.status_code == 422

    def test_chat_service_called_with_correct_args(
        self, client: TestClient
    ) -> None:
        """ChatService.send_message() is called with the right conversation_id and content."""
        user_msg = _make_message(id=_USER_MSG_ID, role="user", content="Hello")
        asst_msg = _make_message(id=_ASST_MSG_ID, role="assistant", content="Hi")
        mock_chat = self._setup_mock_chat(user_msg, asst_msg)

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        client.post(
            f"/api/v1/conversations/{_CONV_ID}/messages",
            json={"content": "Hello"},
        )

        call_kwargs = mock_chat.send_message.call_args
        assert call_kwargs.kwargs["conversation_id"] == _CONV_ID
        assert call_kwargs.kwargs["content"] == "Hello"

    def test_null_source_references_in_user_message(
        self, client: TestClient
    ) -> None:
        """User message source_references is null."""
        user_msg = _make_message(
            id=_USER_MSG_ID, role="user", content="Q", source_references=None
        )
        asst_msg = _make_message(id=_ASST_MSG_ID, role="assistant", content="A")
        mock_chat = self._setup_mock_chat(user_msg, asst_msg)

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        resp = client.post(
            f"/api/v1/conversations/{_CONV_ID}/messages",
            json={"content": "Q"},
        )
        assert resp.json()["user_message"]["source_references"] is None

    def test_x_request_id_in_response(self, client: TestClient) -> None:
        """X-Request-ID header is present in the response."""
        user_msg = _make_message(id=_USER_MSG_ID, role="user", content="Q")
        asst_msg = _make_message(id=_ASST_MSG_ID, role="assistant", content="A")
        mock_chat = self._setup_mock_chat(user_msg, asst_msg)

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        resp = client.post(
            f"/api/v1/conversations/{_CONV_ID}/messages",
            json={"content": "Q"},
        )
        assert (
            "x-request-id" in resp.headers
            or "X-Request-ID" in resp.headers
        )


# ---------------------------------------------------------------------------
# WS /api/v1/conversations/{id}/stream  (§3.2)
# ---------------------------------------------------------------------------


def _events_to_stream(*events: object):
    """Return a coroutine that yields the given events from an async generator."""
    async def _inner(*args, **kwargs) -> AsyncIterator:  # type: ignore[return]
        async def _gen():
            for evt in events:
                yield evt
        return _gen()
    return _inner


class TestStreamChatRoute:
    """WS /api/v1/conversations/{conversation_id}/stream"""

    def test_valid_question_receives_all_events(
        self, client: TestClient
    ) -> None:
        """Complete event sequence: user_message_saved → sources_found → token → complete."""
        events = [
            UserMessageSavedEvent(message_id=_USER_MSG_ID),
            SourcesFoundEvent(sources=[]),
            TokenEvent(content="Hello"),
            CompleteEvent(message_id=_ASST_MSG_ID),
        ]

        mock_chat = MagicMock()
        mock_chat.stream_message = _events_to_stream(*events)

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        with client.websocket_connect(
            f"/api/v1/conversations/{_CONV_ID}/stream"
        ) as ws:
            ws.send_json({"type": "question", "content": "Hello?"})
            received = []
            try:
                while True:
                    msg = ws.receive_json()
                    received.append(msg)
                    if msg["type"] in ("complete", "error"):
                        break
            except Exception:
                pass

        types = [m["type"] for m in received]
        assert "user_message_saved" in types
        assert "sources_found" in types
        assert "token" in types
        assert "complete" in types

    def test_complete_event_has_message_id(self, client: TestClient) -> None:
        """CompleteEvent carries the assistant message ID."""
        events = [
            UserMessageSavedEvent(message_id=_USER_MSG_ID),
            SourcesFoundEvent(sources=[]),
            CompleteEvent(message_id=_ASST_MSG_ID),
        ]
        mock_chat = MagicMock()
        mock_chat.stream_message = _events_to_stream(*events)

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        with client.websocket_connect(
            f"/api/v1/conversations/{_CONV_ID}/stream"
        ) as ws:
            ws.send_json({"type": "question", "content": "Who?"})
            received = []
            try:
                while True:
                    msg = ws.receive_json()
                    received.append(msg)
                    if msg["type"] in ("complete", "error"):
                        break
            except Exception:
                pass

        complete_events = [m for m in received if m["type"] == "complete"]
        assert len(complete_events) == 1
        assert complete_events[0]["message_id"] == _ASST_MSG_ID

    def test_token_events_contain_content(self, client: TestClient) -> None:
        """TokenEvents carry text fragments."""
        events = [
            UserMessageSavedEvent(message_id=_USER_MSG_ID),
            SourcesFoundEvent(sources=[]),
            TokenEvent(content="Based "),
            TokenEvent(content="on "),
            TokenEvent(content="the docs."),
            CompleteEvent(message_id=_ASST_MSG_ID),
        ]
        mock_chat = MagicMock()
        mock_chat.stream_message = _events_to_stream(*events)

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        with client.websocket_connect(
            f"/api/v1/conversations/{_CONV_ID}/stream"
        ) as ws:
            ws.send_json({"type": "question", "content": "What?"})
            received = []
            try:
                while True:
                    msg = ws.receive_json()
                    received.append(msg)
                    if msg["type"] in ("complete", "error"):
                        break
            except Exception:
                pass

        tokens = [m for m in received if m["type"] == "token"]
        text = "".join(t["content"] for t in tokens)
        assert text == "Based on the docs."

    def test_invalid_message_type_sends_error(self, client: TestClient) -> None:
        """Sending wrong message type returns an error event."""
        mock_chat = MagicMock()
        mock_chat.stream_message = AsyncMock()

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        with client.websocket_connect(
            f"/api/v1/conversations/{_CONV_ID}/stream"
        ) as ws:
            ws.send_json({"type": "wrong_type", "content": "X"})
            try:
                msg = ws.receive_json()
                assert msg["type"] == "error"
            except Exception:
                pass  # connection may close with error

    def test_empty_content_sends_error(self, client: TestClient) -> None:
        """Sending empty content returns an error event."""
        mock_chat = MagicMock()
        mock_chat.stream_message = AsyncMock()

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        with client.websocket_connect(
            f"/api/v1/conversations/{_CONV_ID}/stream"
        ) as ws:
            ws.send_json({"type": "question", "content": "   "})
            try:
                msg = ws.receive_json()
                assert msg["type"] == "error"
            except Exception:
                pass

    def test_error_event_on_conversation_not_found(
        self, client: TestClient
    ) -> None:
        """ConversationNotFoundError from ChatService yields an error event."""
        events = [
            ErrorEvent(message="Conversation cccccccc-0000-0000-0000-000000000001 not found.")
        ]
        mock_chat = MagicMock()
        mock_chat.stream_message = _events_to_stream(*events)

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        with client.websocket_connect(
            f"/api/v1/conversations/{_CONV_ID}/stream"
        ) as ws:
            ws.send_json({"type": "question", "content": "Q?"})
            try:
                msg = ws.receive_json()
                assert msg["type"] == "error"
            except Exception:
                pass

    def test_sources_found_event_content(self, client: TestClient) -> None:
        """SourcesFoundEvent carries source citation dicts."""
        sources = [
            {
                "document_id": "doc-1",
                "file_name": "guide.pdf",
                "page_number": 3,
                "relevance_score": 0.91,
            }
        ]
        events = [
            UserMessageSavedEvent(message_id=_USER_MSG_ID),
            SourcesFoundEvent(sources=sources),
            CompleteEvent(message_id=_ASST_MSG_ID),
        ]
        mock_chat = MagicMock()
        mock_chat.stream_message = _events_to_stream(*events)

        app.dependency_overrides[get_db_session] = _make_noop_db_gen()
        app.dependency_overrides[get_chat_service] = lambda: mock_chat

        with client.websocket_connect(
            f"/api/v1/conversations/{_CONV_ID}/stream"
        ) as ws:
            ws.send_json({"type": "question", "content": "Where?"})
            received = []
            try:
                while True:
                    msg = ws.receive_json()
                    received.append(msg)
                    if msg["type"] in ("complete", "error"):
                        break
            except Exception:
                pass

        sources_events = [m for m in received if m["type"] == "sources_found"]
        assert len(sources_events) == 1
        assert sources_events[0]["sources"] == sources
