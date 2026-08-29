"""System routes — health and configuration endpoints.

Routes
------
GET /api/v1/health  — Component status + re-embedding indicator (FR-021)
GET /api/v1/config  — Non-sensitive application configuration
"""
from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.core.logging import get_logger

router = APIRouter(prefix="/api/v1", tags=["system"])

log = get_logger(__name__)

# Module-level reference to the ModelManager singleton — set by app.main after
# init.  We use a dict wrapper to allow reassignment from within main.py.
_model_manager_ref: dict[str, object] = {"manager": None}


def set_model_manager(manager: object) -> None:
    """Called once from main.py lifespan to inject the ModelManager."""
    _model_manager_ref["manager"] = manager


@router.get("/health", summary="Application and component health check")
async def get_health() -> dict[str, object]:
    """Return live component statuses.

    Response shape (per api-contracts.md §5.1)::

        {
          "status": "ok",
          "database": "ok",
          "embedding_model": "nomic-embed-text-v1.5",
          "llm_model": "phi3.5:3.8b-mini-instruct-q4_K_M",
          "ollama": "ok" | "unavailable",
          "reembedding": false
        }
    """
    manager = _model_manager_ref["manager"]
    if manager is not None:
        from app.services.model_manager import ModelManager

        if isinstance(manager, ModelManager):
            status = await manager.health_status()
            return status

    # Fallback if manager not yet initialised
    return {
        "status": "ok",
        "database": "ok",
        "embedding_model": settings.embedding_model,
        "llm_model": settings.llm_model,
        "ollama": "unknown",
        "reembedding": False,
    }


@router.get("/config", summary="Non-sensitive application configuration")
async def get_config() -> dict[str, object]:
    """Return non-sensitive configuration values.

    Sensitive fields (passwords, API keys, full database URLs) are omitted.
    Response shape (per api-contracts.md §5.2)::

        {
          "host": "127.0.0.1",
          "port": 8000,
          "embedding_provider": "sentence-transformers",
          "embedding_model": "nomic-embed-text-v1.5",
          "embedding_dimensions": 768,
          "llm_provider": "ollama",
          "llm_model": "phi3.5:3.8b-mini-instruct-q4_K_M",
          "llm_base_url": "http://localhost:11434",
          "llm_context_window": 4096,
          "retrieval_top_k": 5,
          "retrieval_similarity_threshold": 0.7,
          "chunk_size": 1000,
          "chunk_overlap": 200,
          "sliding_window_messages": 10,
          "chroma_collection_name": "knowledge_base",
          "log_level": "INFO"
        }
    """
    log.info("config_requested")
    return {
        "host": settings.host,
        "port": settings.port,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm_base_url": settings.llm_base_url,
        "llm_context_window": settings.llm_context_window,
        "retrieval_top_k": settings.retrieval_top_k,
        "retrieval_similarity_threshold": settings.retrieval_similarity_threshold,
        "chunk_size": settings.chunk_size,
        "chunk_overlap": settings.chunk_overlap,
        "sliding_window_messages": settings.sliding_window_messages,
        "chroma_collection_name": settings.chroma_collection_name,
        "log_level": settings.log_level,
    }
