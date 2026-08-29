"""Domain exception hierarchy for the Knowledge Base application.

All custom exceptions inherit from ``AppError``, which carries:

- ``message`` — human-readable description (also the HTTP response detail)
- ``code``    — machine-readable error code string (e.g. ``"document_not_found"``)
- ``status_code`` — suggested HTTP status code for API responses

Usage
-----
    from app.core.exceptions import DocumentNotFoundError

    raise DocumentNotFoundError(document_id=42)

FastAPI exception handlers (registered in ``app.main``) convert these to
structured JSON responses::

    {
        "error": "document_not_found",
        "detail": "Document 42 not found.",
        "request_id": "..."
    }
"""
from __future__ import annotations

from http import HTTPStatus


class AppError(Exception):
    """Base class for all application-level errors.

    Parameters
    ----------
    message:
        Human-readable error description returned in the HTTP response body.
    code:
        Machine-readable snake_case identifier for the error type.
    status_code:
        HTTP status code to use when this exception propagates to an API
        endpoint.  Defaults to 500 (Internal Server Error).
    """

    def __init__(
        self,
        message: str,
        code: str = "internal_error",
        status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(code={self.code!r}, message={self.message!r})"


# ---------------------------------------------------------------------------
# 404 Not Found
# ---------------------------------------------------------------------------


class DocumentNotFoundError(AppError):
    """Raised when a requested document does not exist in the database."""

    def __init__(self, document_id: int | str) -> None:
        super().__init__(
            message=f"Document {document_id} not found.",
            code="document_not_found",
            status_code=HTTPStatus.NOT_FOUND,
        )
        self.document_id = document_id


class ConversationNotFoundError(AppError):
    """Raised when a requested conversation does not exist in the database."""

    def __init__(self, conversation_id: int | str) -> None:
        super().__init__(
            message=f"Conversation {conversation_id} not found.",
            code="conversation_not_found",
            status_code=HTTPStatus.NOT_FOUND,
        )
        self.conversation_id = conversation_id


class IngestionJobNotFoundError(AppError):
    """Raised when a requested ingestion job does not exist in the database."""

    def __init__(self, job_id: str) -> None:
        super().__init__(
            message=f"Ingestion job '{job_id}' not found.",
            code="ingestion_job_not_found",
            status_code=HTTPStatus.NOT_FOUND,
        )
        self.job_id = job_id


# ---------------------------------------------------------------------------
# 409 Conflict
# ---------------------------------------------------------------------------


class IngestionConflictError(AppError):
    """Raised when a new ingestion job is requested while one is already running.

    Maps to **FR-022** (single ingestion job enforcement).
    """

    def __init__(self, job_id: str | int | None = None) -> None:
        detail = (
            f"Ingestion job {job_id} is already in progress."
            if job_id is not None
            else "An ingestion job is already in progress."
        )
        super().__init__(
            message=detail,
            code="ingestion_conflict",
            status_code=HTTPStatus.CONFLICT,
        )
        self.job_id = job_id


# ---------------------------------------------------------------------------
# 422 Unprocessable Entity / 400 Bad Request
# ---------------------------------------------------------------------------


class ValidationError(AppError):
    """Raised for domain-level validation failures not covered by Pydantic.

    Examples
    --------
    - chunk_overlap >= chunk_size
    - unsupported document format
    - empty query string
    """

    def __init__(self, message: str, field: str | None = None) -> None:
        super().__init__(
            message=message,
            code="validation_error",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
        self.field = field


class PathValidationError(AppError):
    """Raised when a supplied file-system path fails safety checks.

    Maps to **FR-023** (path validation with symlink resolution).

    Checks performed by the ingestion service before accepting a path:
    1. Path is not empty.
    2. Resolved path (``os.path.realpath``) is a directory.
    3. Directory is readable by the current process.
    """

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(
            message=f"Invalid knowledge folder path '{path}': {reason}",
            code="path_validation_error",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
        self.path = path
        self.reason = reason


# ---------------------------------------------------------------------------
# 503 Service Unavailable
# ---------------------------------------------------------------------------


class ModelUnavailableError(AppError):
    """Raised when the embedding or LLM model cannot be reached or loaded.

    Examples
    --------
    - Ollama server is not running.
    - sentence-transformers model files are missing / corrupt.
    - HTTP timeout contacting the model endpoint.
    """

    def __init__(self, model: str, reason: str) -> None:
        super().__init__(
            message=f"Model '{model}' is unavailable: {reason}",
            code="model_unavailable",
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
        )
        self.model = model
        self.reason = reason


# ---------------------------------------------------------------------------
# Summary-specific errors
# ---------------------------------------------------------------------------


class SummaryNotFoundError(AppError):
    """Raised when no cached summary exists for the requested document."""

    def __init__(self, document_id: str) -> None:
        super().__init__(
            message=f"No summary found for document {document_id}.",
            code="summary_not_found",
            status_code=HTTPStatus.NOT_FOUND,
        )
        self.document_id = document_id


class DocumentNotReadyError(AppError):
    """Raised when a summary is requested for a document not yet ingested.

    Maps to the 409 branch in api-contracts.md §4.1:
    ``409 — Document not yet ingested (status != completed)``.
    """

    def __init__(self, document_id: str, status: str) -> None:
        super().__init__(
            message=(
                f"Document {document_id} is not ready for summarization "
                f"(current status: '{status}'). Ingest the document first."
            ),
            code="document_not_ready",
            status_code=HTTPStatus.CONFLICT,
        )
        self.document_id = document_id
        self.status = status
