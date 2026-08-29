"""FastAPI application entry point.

Startup sequence (lifespan)
---------------------------
1. Configure structured logging
2. Initialise database (create tables if missing)
3. Initialise singleton providers and vector store
4. Start ModelManager (warm-up, Ollama check, FR-021 version check)

Middleware
----------
- **CORSMiddleware** — allow frontend dev server (localhost:5173) and same-origin
- **RequestIDMiddleware** — generate/propagate X-Request-ID, bind to structlog context

Routes (all under /api/v1)
--------------------------
- /health, /config          — system.py
- /ingestion/*              — ingestion.py  (added in Phase 3)
- /documents/*              — documents.py  (added in Phase 3)
- /conversations/*          — conversations.py (added in Phase 4)
- /conversations/{id}/messages, WS stream — chat.py (added in Phase 4)
- /documents/{id}/summary   — summary.py   (added in Phase 5)
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import init_singletons, get_singleton_embedding_provider, get_singleton_llm_provider, get_singleton_vector_store
from app.api.routes import system
from app.config import settings
from app.core.exceptions import AppError
from app.core.logging import configure_logging, get_logger
from app.db.database import close_db, init_db
from app.services.model_manager import ModelManager

import structlog

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle for the application."""
    # -- Startup --
    configure_logging(level=settings.log_level, fmt=settings.log_format)
    log.info("application_startup", host=settings.host, port=settings.port)

    await init_db()

    init_singletons()

    vector_store = get_singleton_vector_store()
    embedding_provider = get_singleton_embedding_provider()
    llm_provider = get_singleton_llm_provider()

    manager = ModelManager(
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        llm_provider=llm_provider,
    )
    await manager.startup()

    # Inject manager into system routes for /health endpoint
    system.set_model_manager(manager)

    log.info("application_ready")
    yield

    # -- Shutdown --
    log.info("application_shutdown")
    await close_db()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Knowledge Base AI",
    description="Local NotebookLM-like application — REST API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

_ALLOWED_ORIGINS = [
    "http://localhost:5173",   # Vite dev server
    "http://127.0.0.1:5173",
    "http://localhost:3000",   # alternate dev port
    f"http://localhost:{settings.port}",
    f"http://127.0.0.1:{settings.port}",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# ---------------------------------------------------------------------------
# Request-ID middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: object) -> Response:
    """Generate or propagate X-Request-ID and bind it to the structlog context."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(request_id=request_id)

    response: Response = await call_next(request)  # type: ignore[operator]
    response.headers["X-Request-ID"] = request_id
    structlog.contextvars.clear_contextvars()
    return response


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------


from fastapi.responses import JSONResponse  # noqa: E402


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert domain exceptions into structured JSON error responses.

    Response shape (per api-contracts.md §6)::

        {
            "error": {
                "code": "document_not_found",
                "message": "Document 42 not found.",
                "request_id": "...",
                "details": null
            }
        }
    """
    request_id = request.headers.get("X-Request-ID", "")
    log.warning(
        "app_error",
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
                "details": None,
            }
        },
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unexpected errors — return 500 without leaking internals."""
    request_id = request.headers.get("X-Request-ID", "")
    log.error(
        "unhandled_error",
        error=str(exc),
        request_id=request_id,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred. Please check server logs.",
                "request_id": request_id,
                "details": None,
            }
        },
        headers={"X-Request-ID": request_id},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(system.router)

# Phase 3 routes
from app.api.routes import ingestion  # noqa: E402
app.include_router(ingestion.router)

from app.api.routes import documents  # noqa: E402
app.include_router(documents.router)

# Phase 4 routes (US2 — Conversational Q&A)
from app.api.routes import conversations  # noqa: E402
app.include_router(conversations.router)

from app.api.routes import chat  # noqa: E402
app.include_router(chat.router)

# Phase 5 routes (US4 — On-demand document summarization)
from app.api.routes import summary  # noqa: E402
app.include_router(summary.router)
