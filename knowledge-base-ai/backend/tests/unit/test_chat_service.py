"""Unit tests for ChatService — T046.

Strategy:
- Pure helpers (_build_context_text, _build_prompt, _build_source_references):
  tested with no mocks.
- ChatService.send_message / stream_message:
  - SQLAlchemy AsyncSession replaced by AsyncMock with side_effect lists
    to handle multiple db.execute() calls in one request.
  - RetrievalService replaced by AsyncMock (no real ChromaDB).
  - LLMProvider replaced by _StubLLMProvider.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from collections.abc import AsyncIterator

from app.core.exceptions import ConversationNotFoundError, ModelUnavailableError
from app.models.conversation import Conversation
from app.models.message import Message
from app.providers.base import LLMProvider
from app.services.chat import (
    ChatService,
    CompleteEvent,
    ErrorEvent,
    SourcesFoundEvent,
    TokenEvent,
    UserMessageSavedEvent,
    _build_context_text,
    _build_prompt,
    _build_source_references,
    _NO_CONTEXT_NOTE,
)
from app.services.retrieval import RetrievalResult, RetrievalService, SourceReference


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_result(
    chunk_id: str = "doc1_0",
    document_id: str = "doc-1",
    file_name: str = "arch.pdf",
    page_number: int | None = 3,
    relevance_score: float = 0.92,
    text: str = "Architecture principles text.",
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        file_name=file_name,
        file_path=f"/docs/{file_name}",
        text=text,
        chunk_index=0,
        total_chunks=5,
        page_number=page_number,
        relevance_score=relevance_score,
    )


def _make_conversation(
    conv_id: str = "conv-1",
    message_count: int = 0,
) -> Conversation:
    convo = MagicMock(spec=Conversation)
    convo.id = conv_id
    convo.message_count = message_count
    convo.title = None
    convo.preview = None
    return convo


class _StubLLMProvider(LLMProvider):
    """LLMProvider that returns a fixed string and streams fixed tokens."""

    def __init__(
        self,
        response: str = "The architecture uses a layered pattern.",
        tokens: list[str] | None = None,
        raise_on_generate: Exception | None = None,
        raise_on_stream: Exception | None = None,
    ) -> None:
        self._response = response
        self._tokens = tokens or ["The ", "answer ", "is ", "42."]
        self._raise_on_generate = raise_on_generate
        self._raise_on_stream = raise_on_stream

    async def generate(self, prompt: str, context: str = "") -> str:
        if self._raise_on_generate:
            raise self._raise_on_generate
        return self._response

    async def stream(self, prompt: str, context: str = "") -> AsyncIterator[str]:
        return self._stream_tokens()

    async def _stream_tokens(self) -> AsyncIterator[str]:  # type: ignore[misc]
        if self._raise_on_stream:
            raise self._raise_on_stream
        for token in self._tokens:
            yield token

    @property
    def model_version(self) -> str:
        return "stub-llm-v1"


def _make_db_mock(
    conversation: Conversation | None,
    history_messages: list[Message] | None = None,
) -> AsyncMock:
    """Build an AsyncSession mock that serves two execute() calls:
    1st: conversation lookup (scalar_one_or_none)
    2nd: history lookup (scalars().all())
    """
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    conv_result = MagicMock()
    conv_result.scalar_one_or_none.return_value = conversation

    hist_messages = history_messages or []
    hist_result = MagicMock()
    hist_scalars = MagicMock()
    hist_scalars.all.return_value = hist_messages
    hist_result.scalars.return_value = hist_scalars

    db.execute.side_effect = [conv_result, hist_result]
    return db


def _make_service(
    llm: LLMProvider | None = None,
    retrieval_results: list[RetrievalResult] | None = None,
) -> ChatService:
    retrieval = MagicMock(spec=RetrievalService)
    retrieval.retrieve = AsyncMock(return_value=retrieval_results or [])
    provider = llm or _StubLLMProvider()
    return ChatService(retrieval_service=retrieval, llm_provider=provider)


# ---------------------------------------------------------------------------
# _build_context_text
# ---------------------------------------------------------------------------

class TestBuildContextText:
    def test_returns_no_context_note_when_empty(self) -> None:
        text = _build_context_text([])
        assert text == _NO_CONTEXT_NOTE

    def test_includes_file_name_and_text(self) -> None:
        r = _make_result(file_name="arch.pdf", page_number=5, text="Important content.")
        text = _build_context_text([r])
        assert "arch.pdf" in text
        assert "page 5" in text
        assert "Important content." in text

    def test_omits_page_when_none(self) -> None:
        r = _make_result(file_name="notes.md", page_number=None)
        text = _build_context_text([r])
        assert "page" not in text
        assert "notes.md" in text

    def test_multiple_results_separated(self) -> None:
        r1 = _make_result(chunk_id="a", file_name="a.pdf", text="Alpha.")
        r2 = _make_result(chunk_id="b", file_name="b.md", text="Beta.")
        text = _build_context_text([r1, r2])
        assert "Alpha." in text
        assert "Beta." in text
        # Separated by double newline
        assert "\n\n" in text


# ---------------------------------------------------------------------------
# _build_prompt
# ---------------------------------------------------------------------------

class TestBuildPrompt:
    def test_contains_user_question(self) -> None:
        prompt = _build_prompt("What is X?", history_text="")
        assert "What is X?" in prompt

    def test_no_history_section_when_empty(self) -> None:
        prompt = _build_prompt("What is X?", history_text="")
        assert "Conversation history" not in prompt

    def test_includes_history_when_present(self) -> None:
        prompt = _build_prompt("Follow-up?", history_text="User: first\nAssistant: reply")
        assert "Conversation history" in prompt
        assert "User: first" in prompt
        assert "Assistant: reply" in prompt

    def test_system_prompt_included(self) -> None:
        prompt = _build_prompt("Q?", history_text="")
        assert "knowledge base" in prompt.lower()


# ---------------------------------------------------------------------------
# _build_source_references
# ---------------------------------------------------------------------------

class TestBuildSourceReferences:
    def test_empty_returns_empty(self) -> None:
        assert _build_source_references([]) == []

    def test_single_result(self) -> None:
        r = _make_result(document_id="d1", page_number=3, relevance_score=0.9)
        refs = _build_source_references([r])
        assert len(refs) == 1
        assert refs[0].document_id == "d1"
        assert refs[0].page_number == 3

    def test_deduplicates_by_document_id_and_page(self) -> None:
        # Same document_id + page_number → keep higher score
        r1 = _make_result(chunk_id="a", document_id="d1", page_number=3, relevance_score=0.9)
        r2 = _make_result(chunk_id="b", document_id="d1", page_number=3, relevance_score=0.7)
        refs = _build_source_references([r1, r2])
        assert len(refs) == 1
        assert refs[0].relevance_score == 0.9

    def test_different_pages_kept_separately(self) -> None:
        r1 = _make_result(chunk_id="a", document_id="d1", page_number=3)
        r2 = _make_result(chunk_id="b", document_id="d1", page_number=5)
        refs = _build_source_references([r1, r2])
        assert len(refs) == 2

    def test_sorted_by_relevance_descending(self) -> None:
        r1 = _make_result(chunk_id="a", document_id="d1", page_number=1, relevance_score=0.7)
        r2 = _make_result(chunk_id="b", document_id="d2", page_number=2, relevance_score=0.95)
        refs = _build_source_references([r1, r2])
        assert refs[0].relevance_score > refs[1].relevance_score

    def test_returns_source_reference_instances(self) -> None:
        r = _make_result()
        refs = _build_source_references([r])
        assert all(isinstance(ref, SourceReference) for ref in refs)


# ---------------------------------------------------------------------------
# ChatEvent dataclasses
# ---------------------------------------------------------------------------

class TestChatEvents:
    def test_user_message_saved_type(self) -> None:
        e = UserMessageSavedEvent(message_id="m1")
        assert e.type == "user_message_saved"
        assert e.message_id == "m1"

    def test_sources_found_type(self) -> None:
        e = SourcesFoundEvent(sources=[{"file_name": "a.pdf"}])
        assert e.type == "sources_found"
        assert e.sources[0]["file_name"] == "a.pdf"

    def test_token_event_type(self) -> None:
        e = TokenEvent(content="hello ")
        assert e.type == "token"
        assert e.content == "hello "

    def test_complete_event_type(self) -> None:
        e = CompleteEvent(message_id="m2")
        assert e.type == "complete"
        assert e.message_id == "m2"

    def test_error_event_type(self) -> None:
        e = ErrorEvent(message="oops")
        assert e.type == "error"
        assert e.message == "oops"


# ---------------------------------------------------------------------------
# ChatService.send_message
# ---------------------------------------------------------------------------

class TestChatServiceSendMessage:
    @pytest.mark.asyncio
    async def test_happy_path_returns_both_messages(self) -> None:
        convo = _make_conversation()
        db = _make_db_mock(convo)
        svc = _make_service(retrieval_results=[_make_result()])

        user_msg, asst_msg = await svc.send_message(db, "conv-1", "What is X?")

        assert user_msg.role == "user"
        assert user_msg.content == "What is X?"
        assert asst_msg.role == "assistant"
        assert asst_msg.content != ""

    @pytest.mark.asyncio
    async def test_raises_conversation_not_found(self) -> None:
        db = _make_db_mock(conversation=None)
        svc = _make_service()
        with pytest.raises(ConversationNotFoundError):
            await svc.send_message(db, "bad-id", "Hi")

    @pytest.mark.asyncio
    async def test_persists_user_message_before_retrieval(self) -> None:
        """db.add must be called for the user message even if retrieval fails."""
        convo = _make_conversation()
        db = _make_db_mock(convo)

        retrieval = MagicMock(spec=RetrievalService)
        retrieval.retrieve = AsyncMock(return_value=[])
        svc = ChatService(retrieval_service=retrieval, llm_provider=_StubLLMProvider())

        await svc.send_message(db, "conv-1", "What is X?")
        assert db.add.call_count == 2  # user + assistant

    @pytest.mark.asyncio
    async def test_no_relevant_context_still_returns_answer(self) -> None:
        """When retrieval is empty the LLM should still get a prompt and respond."""
        convo = _make_conversation()
        db = _make_db_mock(convo)
        svc = _make_service(retrieval_results=[])  # empty

        user_msg, asst_msg = await svc.send_message(db, "conv-1", "Off-topic question")
        assert asst_msg.content != ""
        assert asst_msg.source_references is None  # no refs

    @pytest.mark.asyncio
    async def test_source_references_stored_on_assistant_message(self) -> None:
        convo = _make_conversation()
        db = _make_db_mock(convo)
        r = _make_result(document_id="doc-42", file_name="arch.pdf", page_number=7)
        svc = _make_service(retrieval_results=[r])

        _, asst_msg = await svc.send_message(db, "conv-1", "Q?")

        assert asst_msg.source_references is not None
        assert len(asst_msg.source_references) == 1
        assert asst_msg.source_references[0]["document_id"] == "doc-42"
        assert asst_msg.source_references[0]["file_name"] == "arch.pdf"
        assert asst_msg.source_references[0]["page_number"] == 7

    @pytest.mark.asyncio
    async def test_conversation_title_set_on_first_message(self) -> None:
        convo = _make_conversation(message_count=0)
        db = _make_db_mock(convo)
        svc = _make_service()

        await svc.send_message(db, "conv-1", "What is the architecture?")

        assert convo.title == "What is the architecture?"
        assert convo.preview == "What is the architecture?"

    @pytest.mark.asyncio
    async def test_conversation_message_count_incremented(self) -> None:
        convo = _make_conversation(message_count=4)
        db = _make_db_mock(convo)
        svc = _make_service()

        await svc.send_message(db, "conv-1", "Q?")
        assert convo.message_count == 6  # +2

    @pytest.mark.asyncio
    async def test_db_commit_called(self) -> None:
        convo = _make_conversation()
        db = _make_db_mock(convo)
        svc = _make_service()

        await svc.send_message(db, "conv-1", "Q?")
        db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_called_with_prompt_containing_question(self) -> None:
        generate_calls: list[tuple[str, str]] = []

        class _TrackingLLM(_StubLLMProvider):
            async def generate(self, prompt: str, context: str = "") -> str:
                generate_calls.append((prompt, context))
                return "answer"

        convo = _make_conversation()
        db = _make_db_mock(convo)
        svc = ChatService(
            retrieval_service=MagicMock(retrieve=AsyncMock(return_value=[])),
            llm_provider=_TrackingLLM(),
        )
        await svc.send_message(db, "conv-1", "Unique question text 123")
        assert any("Unique question text 123" in call[0] for call in generate_calls)

    @pytest.mark.asyncio
    async def test_llm_receives_context_from_retrieval(self) -> None:
        context_received: list[str] = []

        class _TrackingLLM(_StubLLMProvider):
            async def generate(self, prompt: str, context: str = "") -> str:
                context_received.append(context)
                return "answer"

        convo = _make_conversation()
        db = _make_db_mock(convo)
        r = _make_result(text="Specific architecture content.")
        svc = ChatService(
            retrieval_service=MagicMock(retrieve=AsyncMock(return_value=[r])),
            llm_provider=_TrackingLLM(),
        )
        await svc.send_message(db, "conv-1", "Q?")
        assert any("Specific architecture content." in c for c in context_received)


# ---------------------------------------------------------------------------
# ChatService.stream_message
# ---------------------------------------------------------------------------

async def _collect_events(
    svc: ChatService, db: AsyncMock, conv_id: str, content: str
) -> list:
    events = []
    async for event in await svc.stream_message(db, conv_id, content):
        events.append(event)
    return events


class TestChatServiceStreamMessage:
    @pytest.mark.asyncio
    async def test_event_order_happy_path(self) -> None:
        convo = _make_conversation()
        db = _make_db_mock(convo)
        svc = _make_service(
            llm=_StubLLMProvider(tokens=["Hello ", "world"]),
            retrieval_results=[_make_result()],
        )

        events = await _collect_events(svc, db, "conv-1", "Hi?")
        types = [e.type for e in events]

        assert types[0] == "user_message_saved"
        assert types[1] == "sources_found"
        assert "token" in types
        assert types[-1] == "complete"

    @pytest.mark.asyncio
    async def test_all_tokens_emitted(self) -> None:
        tokens = ["The ", "answer ", "is ", "here."]
        convo = _make_conversation()
        db = _make_db_mock(convo)
        svc = _make_service(llm=_StubLLMProvider(tokens=tokens))

        events = await _collect_events(svc, db, "conv-1", "Q?")
        token_events = [e for e in events if isinstance(e, TokenEvent)]
        assert [e.content for e in token_events] == tokens

    @pytest.mark.asyncio
    async def test_conversation_not_found_yields_error_event(self) -> None:
        db = _make_db_mock(conversation=None)
        svc = _make_service()

        events = await _collect_events(svc, db, "bad-id", "Q?")
        assert len(events) == 1
        assert isinstance(events[0], ErrorEvent)
        assert "not found" in events[0].message.lower()

    @pytest.mark.asyncio
    async def test_llm_model_unavailable_yields_error_event(self) -> None:
        convo = _make_conversation()
        db = _make_db_mock(convo)
        svc = _make_service(
            llm=_StubLLMProvider(raise_on_stream=ModelUnavailableError("phi", "not running")),
        )

        events = await _collect_events(svc, db, "conv-1", "Q?")
        error_events = [e for e in events if isinstance(e, ErrorEvent)]
        assert error_events, "Expected at least one ErrorEvent"

    @pytest.mark.asyncio
    async def test_sources_found_event_contains_ref_dicts(self) -> None:
        convo = _make_conversation()
        db = _make_db_mock(convo)
        r = _make_result(document_id="d1", file_name="arch.pdf", page_number=5)
        svc = _make_service(retrieval_results=[r])

        events = await _collect_events(svc, db, "conv-1", "Q?")
        sources_events = [e for e in events if isinstance(e, SourcesFoundEvent)]
        assert sources_events
        sources = sources_events[0].sources
        assert len(sources) == 1
        assert sources[0]["file_name"] == "arch.pdf"
        assert sources[0]["page_number"] == 5

    @pytest.mark.asyncio
    async def test_complete_event_has_message_id(self) -> None:
        convo = _make_conversation()
        db = _make_db_mock(convo)
        svc = _make_service()

        events = await _collect_events(svc, db, "conv-1", "Q?")
        complete_events = [e for e in events if isinstance(e, CompleteEvent)]
        assert complete_events
        assert complete_events[0].message_id != ""

    @pytest.mark.asyncio
    async def test_empty_retrieval_sources_found_empty_list(self) -> None:
        convo = _make_conversation()
        db = _make_db_mock(convo)
        svc = _make_service(retrieval_results=[])

        events = await _collect_events(svc, db, "conv-1", "Off-topic?")
        sources_events = [e for e in events if isinstance(e, SourcesFoundEvent)]
        assert sources_events
        assert sources_events[0].sources == []
