"""Application configuration via Pydantic Settings.

All values are loaded from environment variables or the .env file.
Override defaults by copying .env.example → .env and editing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Knowledge Base application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = Field(default="127.0.0.1", description="Bind address (FR-020)")
    port: int = Field(default=8000, ge=1, le=65535)

    # ── Knowledge Folder ──────────────────────────────────────────────────────
    knowledge_folder: str = Field(
        default="",
        description="Absolute path to the folder containing source documents",
    )

    # ── Embedding ─────────────────────────────────────────────────────────────
    embedding_provider: str = Field(default="sentence-transformers")
    embedding_model: str = Field(default="nomic-embed-text-v1.5")
    embedding_dimensions: int = Field(default=768, gt=0)

    # ── LLM ───────────────────────────────────────────────────────────────────
    llm_provider: str = Field(default="ollama")
    llm_model: str = Field(default="phi3.5:3.8b-mini-instruct-q4_K_M")
    llm_base_url: str = Field(default="http://localhost:11434")
    llm_context_window: int = Field(default=4096, gt=0)
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)

    # ── Retrieval ─────────────────────────────────────────────────────────────
    retrieval_top_k: int = Field(default=5, gt=0)
    retrieval_similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    # ── Chunking ──────────────────────────────────────────────────────────────
    chunk_size: int = Field(default=1000, gt=0)
    chunk_overlap: int = Field(default=200, ge=0)

    # ── Ingestion ─────────────────────────────────────────────────────────────
    min_disk_space_mb: int = Field(
        default=500,
        gt=0,
        description="Minimum free disk space (MB) required before ingestion starts",
    )

    # ── Conversation ──────────────────────────────────────────────────────────
    sliding_window_messages: int = Field(default=10, gt=0)

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/knowledge_base.db",
        description="SQLAlchemy async database URL",
    )

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    chroma_persist_dir: str = Field(default="./data/chromadb")
    chroma_collection_name: str = Field(default="knowledge_base")

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    log_format: Literal["json", "console"] = Field(default="json")

    # ── Validators ────────────────────────────────────────────────────────────
    @field_validator("chunk_overlap")
    @classmethod
    def overlap_smaller_than_chunk(cls, v: int, info: object) -> int:
        """Ensure chunk_overlap < chunk_size to avoid infinite loops."""
        # Access chunk_size from the validated data if available
        data = getattr(info, "data", {})
        chunk_size = data.get("chunk_size", 1000)
        if v >= chunk_size:
            raise ValueError(
                f"chunk_overlap ({v}) must be less than chunk_size ({chunk_size})"
            )
        return v

    @field_validator("knowledge_folder")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        """Normalise folder path — actual existence check is done at ingestion time."""
        return v.rstrip("/").rstrip("\\") if v else v

    @property
    def log_file_path(self) -> Path:
        """Rotating log file location (relative to backend working directory)."""
        return Path("logs") / "app.log"

    @property
    def is_sqlite(self) -> bool:
        """Return True if the configured database is SQLite."""
        return "sqlite" in self.database_url.lower()


# ---------------------------------------------------------------------------
# Module-level singleton — imported everywhere as `from app.config import settings`
# ---------------------------------------------------------------------------
settings = Settings()
