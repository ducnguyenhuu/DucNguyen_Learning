"""Chat REST and WebSocket routes.

Contract: api-contracts.md §3.1, §3.2

POST /api/v1/conversations/{conversation_id}/messages
    — blocking RAG response (§3.1); errors: 404, 503
WS   /api/v1/conversations/{conversation_id}/stream
    — token-streaming RAG response (§3.2)
"""
from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.api.deps import ChatSvc, DbSession
from app.core.logging import get_logger
from app.models.message import Message

router = APIRouter(prefix="/api/v1/conversations", tags=["chat"])

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SendMessageRequest(BaseModel):
    """Request body for POST /conversations/{id}/messages (§3.1)."""

    content: str


class MessageResponse(BaseModel):
    """A single persisted message returned in the chat response (§3.1)."""

    id: str
    role: str
    content: str
    source_references: Optional[list[dict[str, Any]]] = None
    created_at: datetime


class MessagePairResponse(BaseModel):
    """Response for POST /conversations/{id}/messages (§3.1)."""

    user_message: MessageResponse
    assistant_message: MessageResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _message_to_response(msg: Message) -> MessageResponse:
    """Convert an ORM Message to the API response schema."""
    return MessageResponse(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        source_references=msg.source_references,
        created_at=msg.created_at,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post(
    "/{conversation_id}/messages",
    summary="Send a user question and receive an LLM answer (§3.1)",
    response_model=MessagePairResponse,
)
async def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    db: DbSession,
    chat: ChatSvc,
) -> MessagePairResponse:
    """Blocking RAG endpoint — waits for the full LLM response.

    Errors (per api-contracts.md §3.1):
    - 404 if the conversation does not exist
    - 503 if the LLM model is unavailable

    Both ``ConversationNotFoundError`` and ``ModelUnavailableError`` are
    subclasses of ``AppError`` and are converted to structured JSON responses
    by the global exception handler in ``app.main``.
    """
    log.info(
        "chat_send_message",
        conversation_id=conversation_id,
        content_length=len(body.content),
    )

    user_msg, asst_msg = await chat.send_message(
        db=db,
        conversation_id=conversation_id,
        content=body.content,
    )

    return MessagePairResponse(
        user_message=_message_to_response(user_msg),
        assistant_message=_message_to_response(asst_msg),
    )


@router.websocket("/{conversation_id}/stream")
async def stream_chat(
    websocket: WebSocket,
    conversation_id: str,
    db: DbSession,
    chat: ChatSvc,
) -> None:
    """Token-streaming RAG endpoint over WebSocket (§3.2).

    Protocol:
    - Client sends: ``{"type": "question", "content": "..."}``
    - Server streams: user_message_saved → sources_found → token(s) → complete
    - On error: ``{"type": "error", "message": "..."}``
    """
    await websocket.accept()

    # Receive the question -----------------------------------------------
    try:
        data = await websocket.receive_json()
    except WebSocketDisconnect:
        return
    except Exception as exc:
        log.warning(
            "ws_receive_error",
            conversation_id=conversation_id,
            error=str(exc),
        )
        try:
            await websocket.send_json(
                {"type": "error", "message": "Failed to receive message"}
            )
            await websocket.close(code=1003)
        except Exception:
            pass
        return

    # Validate message type -----------------------------------------------
    if (
        not isinstance(data, dict)
        or data.get("type") != "question"
        or not str(data.get("content", "")).strip()
    ):
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Expected JSON: {\"type\": \"question\", \"content\": \"...\"}",
                }
            )
            await websocket.close(code=1003)
        except Exception:
            pass
        return

    content: str = str(data["content"])

    log.info(
        "ws_stream_started",
        conversation_id=conversation_id,
        content_length=len(content),
    )

    # Stream events -------------------------------------------------------
    try:
        async for event in await chat.stream_message(
            db=db,
            conversation_id=conversation_id,
            content=content,
        ):
            try:
                await websocket.send_json(dataclasses.asdict(event))
            except WebSocketDisconnect:
                log.info(
                    "ws_client_disconnected_mid_stream",
                    conversation_id=conversation_id,
                )
                return

    except WebSocketDisconnect:
        log.info("ws_client_disconnected", conversation_id=conversation_id)
        return
    except Exception as exc:
        log.error(
            "ws_stream_error",
            conversation_id=conversation_id,
            error=str(exc),
            exc_info=True,
        )
        try:
            await websocket.send_json({"type": "error", "message": "Internal server error"})
        except Exception:
            pass

    finally:
        try:
            await websocket.close()
        except Exception:
            pass
