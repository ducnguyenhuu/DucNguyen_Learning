"""Integration tests for the ChatService pipeline (T080).

End-to-end:
  - Create a real Conversation in an in-memory SQLite DB.
  - Call ChatService.send_message with mocked Retrieval + LLM.
  - Verify both messages are persisted.
  - Verify source references are stored on the assistant message.
  - Verify the conversation is auto-titled on first message.
  - Verify that a missing conversation raises ConversationNotFoundError.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.exceptions import ConversationNotFoundError
from app.db.database import Base
from app.models.conversation import Conversation
from app.models.message import Message
from app.providers.base import LLMProvider
from app.services.chat import ChatService
from app.services.retrieval import RetrievalResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubLLM(LLMProvider):
    """Minimal LLMProvider that returns a configurable fixed response."""

    def __init__(self, response: str = "The answer is 42.") -> None:
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


def _fake_retrieval_result(
    document_id: str = "doc-1",
    file_name: str = "spec.pdf",
    page_number: int = 3,
    relevance_score: float = 0.92,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=f"{document_id}_0",
        document_id=document_id,
        file_name=file_name,
        file_path=f"/docs/{file_name}",
        text="Relevant content about the topic.",
        chunk_index=0,
        total_chunks=5,
        page_number=page_number,
        relevance_score=relevance_score,
        model_version="test-embed",
    )


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
async def db(test_engine):
    factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with factory() as session:
        yield session


@pytest.fixture
async def conversation(db: AsyncSession) -> Conversation:
    """Persist a fresh Conversation and return it."""
    now = datetime.now(UTC)
    conv = Conversation(
        id=str(uuid.uuid4()),
        title=None,
        preview=None,
        message_count=0,
        created_at=now,
        updated_at=now,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


def _make_chat_service(
    retrieval_results: list[RetrievalResult] | None = None,
    llm_response: str = "Test answer.",
) -> ChatService:
    retrieval_svc = MagicMock()
    retrieval_svc.retrieve = AsyncMock(return_value=retrieval_results or [])
    return ChatService(
        retrieval_service=retrieval_svc,
        llm_provider=_StubLLM(response=llm_response),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSendMessagePersistence:
    """Messages are written to the DB after send_message returns."""

    async def test_user_message_persisted(
        self, db: AsyncSession, conversation: Conversation
    ) -> None:
        svc = _make_chat_service()
        await svc.send_message(db, conversation.id, "What is the capital of France?")

        result = await db.execute(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.role == "user",
            )
        )
        msgs = result.scalars().all()
        assert len(msgs) == 1
        assert msgs[0].content == "What is the capital of France?"

    async def test_assistant_message_persisted(
        self, db: AsyncSession, conversation: Conversation
    ) -> None:
        svc = _make_chat_service(llm_response="Paris.")
        await svc.send_message(db, conversation.id, "Capital?")

        result = await db.execute(
            select(Message).where(
                Message.conversation_id == conversation.id,
                Message.role == "assistant",
            )
        )
        msgs = result.scalars().all()
        assert len(msgs) == 1
        assert msgs[0].content == "Paris."

    async def test_returns_message_pair(
        self, db: AsyncSession, conversation: Conversation
    ) -> None:
        svc = _make_chat_service(llm_response="42")
        user_msg, asst_msg = await svc.send_message(
            db, conversation.id, "What is the answer?"
        )
        assert user_msg.role == "user"
        assert asst_msg.role == "assistant"
        assert asst_msg.content == "42"
        assert user_msg.id is not None
        assert asst_msg.id is not None

    async def test_both_messages_have_conversation_id(
        self, db: AsyncSession, conversation: Conversation
    ) -> None:
        svc = _make_chat_service()
        user_msg, asst_msg = await svc.send_message(db, conversation.id, "Q?")
        assert user_msg.conversation_id == conversation.id
        assert asst_msg.conversation_id == conversation.id


class TestSourceReferences:
    """Source references from retrieval are stored on the assistant message."""

    async def test_source_refs_stored_on_assistant_message(
        self, db: AsyncSession, conversation: Conversation
    ) -> None:
        result = _fake_retrieval_result(document_id="doc-99", page_number=5)
        svc = _make_chat_service(retrieval_results=[result])
        _, asst_msg = await svc.send_message(db, conversation.id, "What does the spec say?")

        assert asst_msg.source_references is not None
        assert len(asst_msg.source_references) == 1
        ref = asst_msg.source_references[0]
        assert ref["document_id"] == "doc-99"
        assert ref["page_number"] == 5

    async def test_no_source_refs_when_retrieval_empty(
        self, db: AsyncSession, conversation: Conversation
    ) -> None:
        svc = _make_chat_service(retrieval_results=[])
        _, asst_msg = await svc.send_message(db, conversation.id, "Q?")

        assert asst_msg.source_references is None or asst_msg.source_references == []

    async def test_source_refs_deduplicated(
        self, db: AsyncSession, conversation: Conversation
    ) -> None:
        """Two results for the same doc + page should produce one source ref."""
        r1 = _fake_retrieval_result(document_id="d1", page_number=2, relevance_score=0.8)
        r2 = _fake_retrieval_result(document_id="d1", page_number=2, relevance_score=0.9)
        svc = _make_chat_service(retrieval_results=[r1, r2])
        _, asst_msg = await svc.send_message(db, conversation.id, "Q?")

        refs = asst_msg.source_references
        assert refs is not None
        assert len(refs) == 1


class TestConversationUpdate:
    """Conversation metadata (title, preview, message_count) updated."""

    async def test_conversation_auto_titled_on_first_message(
        self, db: AsyncSession, conversation: Conversation
    ) -> None:
        assert conversation.title is None
        svc = _make_chat_service()
        await svc.send_message(db, conversation.id, "What is RAG?")

        await db.refresh(conversation)
        assert conversation.title == "What is RAG?"

    async def test_conversation_message_count_incremented(
        self, db: AsyncSession, conversation: Conversation
    ) -> None:
        svc = _make_chat_service()
        await svc.send_message(db, conversation.id, "First question")

        await db.refresh(conversation)
        assert conversation.message_count == 2  # user + assistant

    async def test_title_truncated_to_100_chars(
        self, db: AsyncSession, conversation: Conversation
    ) -> None:
        long_question = "A" * 150
        svc = _make_chat_service()
        await svc.send_message(db, conversation.id, long_question)

        await db.refresh(conversation)
        assert conversation.title is not None
        assert len(conversation.title) == 100

    async def test_title_fixed_after_two_message_pairs(
        self, db: AsyncSession, conversation: Conversation
    ) -> None:
        """After two message pairs (count=4), the title should no longer be updated."""
        svc = _make_chat_service()
        # First two pairs update title (message_count <= 2 at time of update)
        await svc.send_message(db, conversation.id, "First question")
        await svc.send_message(db, conversation.id, "Second question")

        await db.refresh(conversation)
        title_after_two = conversation.title

        # Third pair: message_count is 4 before update → is_first = False → no override
        await svc.send_message(db, conversation.id, "Third question")
        await db.refresh(conversation)

        assert conversation.title == title_after_two


class TestUnknownConversation:
    """Missing conversation ID must raise ConversationNotFoundError."""

    async def test_raises_conversation_not_found(
        self, db: AsyncSession
    ) -> None:
        svc = _make_chat_service()
        with pytest.raises(ConversationNotFoundError):
            await svc.send_message(db, "missing-conv-id-xyz", "Hello")
