"""Structured JSON logging configuration via structlog.

Usage
-----
    from app.core.logging import get_logger, configure_logging

    configure_logging()          # call once at startup (app.main)
    log = get_logger(__name__)   # per-module logger

    log.info("document_ingested", document_id=42, duration_ms=1234)
    log.warning("low_disk_space", available_gb=1.2)
    log.error("parse_failed", file_name="report.pdf", exc_info=True)

Request-scoped context
----------------------
Bind `request_id` (and optionally `job_id`, `conversation_id`) to a
context-local structlog context at the start of every request/task so
every downstream log entry is automatically annotated.

    import structlog
    structlog.contextvars.bind_contextvars(request_id="abc-123")
    # … handle request …
    structlog.contextvars.clear_contextvars()
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog


def _add_app_info(
    logger: Any,  # noqa: ANN401
    method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject static application metadata into every log entry."""
    event_dict.setdefault("app", "knowledge-base-ai")
    return event_dict


def configure_logging(
    level: str = "INFO",
    fmt: str = "json",
    log_file: Path | None = None,
) -> None:
    """Configure structlog + stdlib logging.

    Parameters
    ----------
    level:
        One of DEBUG / INFO / WARNING / ERROR / CRITICAL.
    fmt:
        ``"json"`` for machine-readable output (default, used in production
        and Docker); ``"console"`` for human-friendly colourised output
        during local development.
    log_file:
        Optional path for a rotating file handler (in addition to stdout).
        The parent directory is created automatically if it does not exist.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # ------------------------------------------------------------------
    # stdlib root-logger setup — routes third-party libraries to structlog
    # ------------------------------------------------------------------
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        rotating = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB per file
            backupCount=5,
            encoding="utf-8",
        )
        handlers.append(rotating)

    logging.basicConfig(
        format="%(message)s",
        level=log_level,
        handlers=handlers,
        force=True,
    )

    # Silence noisy third-party loggers unless debugging
    for noisy in ("uvicorn.access", "httpx", "chromadb"):
        logging.getLogger(noisy).setLevel(
            logging.WARNING if level.upper() != "DEBUG" else logging.DEBUG
        )

    # ------------------------------------------------------------------
    # structlog configuration
    # ------------------------------------------------------------------
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        _add_app_info,  # type: ignore[list-item]
    ]

    if fmt == "json":
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog BoundLogger bound to *name*.

    The returned logger automatically includes any context variables bound
    via ``structlog.contextvars.bind_contextvars()``.

    Standard context fields used across the application
    ---------------------------------------------------
    - ``request_id``     — UUID per HTTP request / WebSocket connection
    - ``job_id``         — IngestionJob primary key
    - ``document_id``    — Document primary key
    - ``conversation_id``— Conversation primary key
    - ``file_name``      — Source file being processed
    - ``duration_ms``    — Elapsed time for timed operations
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]
