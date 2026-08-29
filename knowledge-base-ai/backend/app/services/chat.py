"""Chat service — RAG orchestration layer.

This service is the heart of the conversational pipeline.  For every user
question it:

1. **Validates** the conversation exists in the database.
2. **Persists** the user message immediately so it is visible even if the
   LLM call fails.
3. **Retrieves** relevant document chunks via
   :class:`~app.services.retrieval.RetrievalService` (FR-008).
4. **Builds** a structured prompt from the retrieved context, the sliding
   window of recent messages (FR-011), and the current question.
5. **Calls** the :class:`~app.providers.base.LLMProvider` — either blocking
   (``generate``) or streaming (``stream``).
6. **Persists** the assistant message with source references (FR-010).
7. **Updates** the parent :class:`~app.models.conversation.Conversation`
   (``message_count``, ``updated_at``, auto-title and preview on first
   message).

Two public entry points are provided:

- :meth:`ChatService.send_message` — non-streaming, returns the pair
  ``(user_message, assistant_message)`` when complete.  Used by the REST
  POST endpoint (T047).
- :meth:`ChatService.stream_message` — async generator that yields
  :class:`ChatEvent` objects matching the WebSocket protocol (api-contracts
  §3.2).  Used by the WS streaming endpoint (T048).

FR-008 "no relevant information" handling: if retrieval returns no chunks
above the threshold the prompt instructs the LLM to say so explicitly
rather than hallucinating an answer.

Constitution Principle III: Only interface types from ``providers/base.py``
are used here — no concrete providers.
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions import ConversationNotFoundError, ModelUnavailableError
from app.core.logging import get_logger
from app.models.conversation import Conversation
from app.models.message import Message
from app.providers.base import LLMProvider
from app.services.retrieval import RetrievalResult, RetrievalService, SourceReference

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are a helpful, precise AI assistant.  Answer questions exclusively based
on the document context provided below.  If the context does not contain
enough information to answer confidently, say:
"I don't have enough information in the knowledge base to answer that question."
Do NOT invent facts, cite sources outside the context, or speculate beyond
what is explicitly stated in the provided context.
""".strip()

_NO_CONTEXT_NOTE = (
    "No relevant document context was found for this question.  "
    "Inform the user that their question is outside the scope of the "
    "indexed knowledge base."
)

# ---------------------------------------------------------------------------
# Chat event types (used by WebSocket streaming endpoint T048)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UserMessageSavedEvent:
    """Emitted immediately after the user message is persisted."""

    message_id: str
    type: Literal["user_message_saved"] = field(default="user_message_saved", init=False)


@dataclass(frozen=True, slots=True)
class SourcesFoundEvent:
    """Emitted after retrieval — carries compact source citations."""

    sources: list[dict[str, Any]]  # list[SourceReference.to_dict()]
    type: Literal["sources_found"] = field(default="sources_found", init=False)


@dataclass(frozen=True, slots=True)
class TokenEvent:
    """Carries a single streamed LLM token / text fragment."""

    content: str
    type: Literal["token"] = field(default="token", init=False)


@dataclass(frozen=True, slots=True)
class CompleteEvent:
    """Emitted once the assistant message has been fully persisted."""

    message_id: str
    type: Literal["complete"] = field(default="complete", init=False)


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    """Emitted on unrecoverable errors during streaming."""

    message: str
    type: Literal["error"] = field(default="error", init=False)


# Union type used as the yield type for stream_message
ChatEvent = (
    UserMessageSavedEvent
    | SourcesFoundEvent
    | TokenEvent
    | CompleteEvent
    | ErrorEvent
)

# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ChatService:
    """RAG orchestration service.

    Parameters
    ----------
    retrieval_service:
        Performs semantic search over ChromaDB.
    llm_provider:
        Generates / streams text completions.
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        llm_provider: LLMProvider,
    ) -> None:
        self._retrieval = retrieval_service
        self._llm = llm_provider

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_message(
        self,
        db: AsyncSession,
        conversation_id: str,
        content: str,
    ) -> tuple[Message, Message]:
        """Process a user question and return both the persisted messages.

        Parameters
        ----------
        db:
            Async SQLAlchemy session (per-request).
        conversation_id:
            UUID of the target conversation.
        content:
            Raw user question text.

        Returns
        -------
        tuple[Message, Message]
            ``(user_message, assistant_message)`` — both already committed.

        Raises
        ------
        ConversationNotFoundError
            If *conversation_id* does not exist.
        ModelUnavailableError
            If the LLM is unreachable. (Propagated from the provider.)
        """
        conversation = await self._get_conversation(db, conversation_id)
        user_msg = await self._persist_user_message(db, conversation, content)

        retrieval_results = await self._retrieve(content)
        context_text = _build_context_text(retrieval_results)
        history_text = await self._build_history_text(db, conversation_id)
        prompt = _build_prompt(content, history_text)

        response_text = await self._llm.generate(prompt=prompt, context=context_text)

        source_refs = _build_source_references(retrieval_results)
        assistant_msg = await self._persist_assistant_message(
            db, conversation, response_text, source_refs
        )
        await self._update_conversation(db, conversation, content, is_first=user_msg is not None and conversation.message_count <= 2)

        log.info(
            "chat_send_message_done",
            conversation_id=conversation_id,
            sources_count=len(source_refs),
        )
        return user_msg, assistant_msg

    async def stream_message(
        self,
        db: AsyncSession,
        conversation_id: str,
        content: str,
    ) -> AsyncIterator[ChatEvent]:
        """Stream an LLM response token-by-token, yielding :class:`ChatEvent` objects.

        Follows the WebSocket protocol from api-contracts.md §3.2:

        1. ``UserMessageSavedEvent`` — after user message is persisted.
        2. ``SourcesFoundEvent``     — after retrieval completes.
        3. N × ``TokenEvent``        — one per streamed token.
        4. ``CompleteEvent``         — after assistant message is persisted.
        5. ``ErrorEvent``            — if an unrecoverable error occurs.

        Note: this is an ``async def`` that returns an ``AsyncIterator``.
        Callers must ``async for event in svc.stream_message(...):``.
        """
        return self._stream_impl(db, conversation_id, content)

    # ------------------------------------------------------------------
    # Internal async generator
    # ------------------------------------------------------------------

    async def _stream_impl(
        self,
        db: AsyncSession,
        conversation_id: str,
        content: str,
    ) -> AsyncIterator[ChatEvent]:
        try:
            conversation = await self._get_conversation(db, conversation_id)
        except ConversationNotFoundError as exc:
            yield ErrorEvent(message=exc.message)
            return

        user_msg = await self._persist_user_message(db, conversation, content)
        yield UserMessageSavedEvent(message_id=user_msg.id)

        try:
            retrieval_results = await self._retrieve(content)
        except Exception as exc:
            log.error("chat_stream_retrieval_failed", error=str(exc))
            yield ErrorEvent(message=f"Retrieval failed: {exc}")
            return

        source_refs = _build_source_references(retrieval_results)
        yield SourcesFoundEvent(sources=[r.to_dict() for r in source_refs])

        context_text = _build_context_text(retrieval_results)
        history_text = await self._build_history_text(db, conversation_id)
        prompt = _build_prompt(content, history_text)

        tokens: list[str] = []
        try:
            async for token in self._llm.stream(prompt=prompt, context=context_text):
                tokens.append(token)
                yield TokenEvent(content=token)
        except ModelUnavailableError as exc:
            log.error("chat_stream_llm_failed", error=str(exc))
            yield ErrorEvent(message=exc.message)
            return
        except Exception as exc:
            log.error("chat_stream_llm_failed", error=str(exc))
            yield ErrorEvent(message=f"LLM error: {exc}")
            return

        full_response = "".join(tokens)
        assistant_msg = await self._persist_assistant_message(
            db, conversation, full_response, source_refs
        )
        await self._update_conversation(
            db, conversation, content, is_first=conversation.message_count <= 2
        )

        yield CompleteEvent(message_id=assistant_msg.id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_conversation(
        self, db: AsyncSession, conversation_id: str
    ) -> Conversation:
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise ConversationNotFoundError(conversation_id)
        return conversation

    async def _persist_user_message(
        self, db: AsyncSession, conversation: Conversation, content: str
    ) -> Message:
        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            role="user",
            content=content,
            source_references=None,
        )
        db.add(msg)
        await db.flush()  # get id without full commit
        log.debug("chat_user_message_saved", message_id=msg.id)
        return msg

    async def _persist_assistant_message(
        self,
        db: AsyncSession,
        conversation: Conversation,
        content: str,
        source_refs: list[SourceReference],
    ) -> Message:
        msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation.id,
            role="assistant",
            content=content,
            source_references=[r.to_dict() for r in source_refs] or None,
        )
        db.add(msg)
        await db.flush()
        log.debug(
            "chat_assistant_message_saved",
            message_id=msg.id,
            sources=len(source_refs),
        )
        return msg

    async def _update_conversation(
        self,
        db: AsyncSession,
        conversation: Conversation,
        user_content: str,
        *,
        is_first: bool,
    ) -> None:
        conversation.message_count += 2  # user + assistant
        conversation.updated_at = datetime.now(UTC)
        if is_first:
            conversation.title = user_content[:100]
            conversation.preview = user_content[:200]
        await db.commit()
        log.debug(
            "conversation_updated",
            conversation_id=conversation.id,
            message_count=conversation.message_count,
        )

    async def _retrieve(self, query: str) -> list[RetrievalResult]:
        try:
            return await self._retrieval.retrieve(query)
        except Exception as exc:
            log.warning("chat_retrieval_error", error=str(exc))
            return []

    async def _build_history_text(
        self, db: AsyncSession, conversation_id: str
    ) -> str:
        """Fetch the sliding window of recent messages and format as text."""
        limit = settings.sliding_window_messages
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        messages = list(reversed(result.scalars().all()))
        if not messages:
            return ""
        lines = []
        for msg in messages:
            role_label = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{role_label}: {msg.content}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Prompt building (module-level, easily testable in isolation)
# ---------------------------------------------------------------------------


def _build_context_text(results: list[RetrievalResult]) -> str:
    """Format retrieved chunks into a context block for the LLM."""
    if not results:
        return _NO_CONTEXT_NOTE
    parts: list[str] = []
    for r in results:
        header = f"[Source: {r.file_name}"
        if r.page_number is not None:
            header += f", page {r.page_number}"
        header += "]"
        parts.append(f"{header}\n{r.text}")
    return "\n\n".join(parts)


def _build_prompt(user_question: str, history_text: str) -> str:
    """Build the full prompt string sent to the LLM.

    The provider is responsible for prepending the *context* (retrieved
    chunks) via its ``context`` parameter, so this function only assembles
    the history + question portion.
    """
    sections: list[str] = [_SYSTEM_PROMPT]
    if history_text:
        sections.append(f"Conversation history:\n{history_text}")
    sections.append(f"User: {user_question}")
    return "\n\n".join(sections)


def _build_source_references(results: list[RetrievalResult]) -> list[SourceReference]:
    """Deduplicate by (document_id, page_number), keep highest score per group."""
    seen: dict[tuple[str, int | None], SourceReference] = {}
    for r in results:
        key = (r.document_id, r.page_number)
        if key not in seen or r.relevance_score > seen[key].relevance_score:
            seen[key] = r.to_source_reference()
    # Return in original relevance order
    unique = list(seen.values())
    unique.sort(key=lambda s: s.relevance_score, reverse=True)
    return unique
