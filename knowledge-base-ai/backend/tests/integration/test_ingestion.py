"""Integration tests for the IngestionService pipeline (T079).

End-to-end:
  - Create a temp folder with sample markdown/text files.
  - Call IngestionService.start_ingestion + run_pipeline.
  - Verify Document rows written to an in-memory SQLite DB.
  - Verify VectorStore.add_chunks was called.
  - Modify / delete a file and re-ingest → verify incremental behaviour.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.database import Base
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.parsers import Chunker
from app.services.embedding import EmbeddingResult, EmbeddingService
from app.services.ingestion import IngestionService

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
def mock_vector_store() -> MagicMock:
    vs = MagicMock()
    vs.add_chunks = AsyncMock()
    vs.delete_by_document_id = AsyncMock()
    vs.query = AsyncMock(return_value=[])
    vs.get_chunks_by_document_id = AsyncMock(return_value=[])
    return vs


@pytest.fixture
def mock_embedding_provider() -> MagicMock:
    """Embedding provider that returns 768-d zero-filled vectors without loading an ML model."""
    provider = MagicMock()
    provider.model_version = "test-embed-v1"
    provider.dimensions = 768

    async def _embed_batch(texts: list[str]) -> list[list[float]]:
        return [[0.01] * 768 for _ in texts]

    provider.embed_batch = _embed_batch
    return provider


@pytest.fixture
def mock_embedding_service(mock_embedding_provider) -> EmbeddingService:
    return EmbeddingService(provider=mock_embedding_provider)


@pytest.fixture
def tmp_docs_folder(tmp_path: Path) -> Path:
    """Temp folder containing two markdown documents."""
    (tmp_path / "intro.md").write_text(
        "# Introduction\n\nThis is the introduction section.\n" * 10
    )
    (tmp_path / "concepts.md").write_text(
        "# Key Concepts\n\nThis section explains key concepts.\n" * 10
    )
    return tmp_path


def _make_svc(
    db: AsyncSession,
    vector_store: MagicMock,
    embedding_service: EmbeddingService,
) -> IngestionService:
    chunker = Chunker(chunk_size=300, chunk_overlap=30)
    return IngestionService(
        db=db,
        vector_store=vector_store,
        embedding_service=embedding_service,
        chunker=chunker,
        min_disk_space_mb=0,  # bypass disk-space check in unit context
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNewFileIngestion:
    """First-run: all files are new."""

    async def test_documents_created_in_db(
        self,
        db: AsyncSession,
        mock_vector_store: MagicMock,
        mock_embedding_service: EmbeddingService,
        tmp_docs_folder: Path,
    ) -> None:
        svc = _make_svc(db, mock_vector_store, mock_embedding_service)
        job = await svc.start_ingestion(str(tmp_docs_folder))
        await db.commit()
        await svc.run_pipeline(job)

        result = await db.execute(select(Document))
        docs = result.scalars().all()
        assert len(docs) == 2
        file_names = {d.file_name for d in docs}
        assert "intro.md" in file_names
        assert "concepts.md" in file_names

    async def test_documents_have_completed_status(
        self,
        db: AsyncSession,
        mock_vector_store: MagicMock,
        mock_embedding_service: EmbeddingService,
        tmp_docs_folder: Path,
    ) -> None:
        svc = _make_svc(db, mock_vector_store, mock_embedding_service)
        job = await svc.start_ingestion(str(tmp_docs_folder))
        await db.commit()
        await svc.run_pipeline(job)

        result = await db.execute(select(Document))
        docs = result.scalars().all()
        for doc in docs:
            assert doc.status == "completed"

    async def test_vector_store_add_chunks_called(
        self,
        db: AsyncSession,
        mock_vector_store: MagicMock,
        mock_embedding_service: EmbeddingService,
        tmp_docs_folder: Path,
    ) -> None:
        svc = _make_svc(db, mock_vector_store, mock_embedding_service)
        job = await svc.start_ingestion(str(tmp_docs_folder))
        await db.commit()
        await svc.run_pipeline(job)

        mock_vector_store.add_chunks.assert_called()

    async def test_job_status_completed_after_pipeline(
        self,
        db: AsyncSession,
        mock_vector_store: MagicMock,
        mock_embedding_service: EmbeddingService,
        tmp_docs_folder: Path,
    ) -> None:
        svc = _make_svc(db, mock_vector_store, mock_embedding_service)
        job = await svc.start_ingestion(str(tmp_docs_folder))
        await db.commit()
        await svc.run_pipeline(job)

        # Refresh from DB
        result = await db.execute(
            select(IngestionJob).where(IngestionJob.id == job.id)
        )
        persisted = result.scalars().first()
        assert persisted is not None
        assert persisted.status == "completed"
        assert persisted.new_files == 2

    async def test_unsupported_extension_skipped(
        self,
        db: AsyncSession,
        mock_vector_store: MagicMock,
        mock_embedding_service: EmbeddingService,
        tmp_docs_folder: Path,
    ) -> None:
        (tmp_docs_folder / "readme.txt").write_text("Plain text content — unsupported.")
        svc = _make_svc(db, mock_vector_store, mock_embedding_service)
        job = await svc.start_ingestion(str(tmp_docs_folder))
        await db.commit()
        await svc.run_pipeline(job)

        result = await db.execute(select(Document))
        docs = result.scalars().all()
        file_names = {d.file_name for d in docs}
        assert "readme.txt" not in file_names
        assert len(docs) == 2  # only intro.md + concepts.md


class TestIncrementalIngestion:
    """Second-run behaviour when files are unchanged / modified / deleted."""

    async def test_unchanged_file_not_re_processed(
        self,
        db: AsyncSession,
        mock_vector_store: MagicMock,
        mock_embedding_service: EmbeddingService,
        tmp_docs_folder: Path,
    ) -> None:
        # First run
        svc = _make_svc(db, mock_vector_store, mock_embedding_service)
        job1 = await svc.start_ingestion(str(tmp_docs_folder))
        await db.commit()
        await svc.run_pipeline(job1)
        first_add_count = mock_vector_store.add_chunks.call_count

        # Second run — nothing changed
        svc2 = _make_svc(db, mock_vector_store, mock_embedding_service)
        job2 = await svc2.start_ingestion(str(tmp_docs_folder))
        await db.commit()
        await svc2.run_pipeline(job2)

        # No new add_chunks calls because both files are unchanged
        assert mock_vector_store.add_chunks.call_count == first_add_count

    async def test_modified_file_re_processed(
        self,
        db: AsyncSession,
        mock_vector_store: MagicMock,
        mock_embedding_service: EmbeddingService,
        tmp_docs_folder: Path,
    ) -> None:
        # First run
        svc = _make_svc(db, mock_vector_store, mock_embedding_service)
        job1 = await svc.start_ingestion(str(tmp_docs_folder))
        await db.commit()
        await svc.run_pipeline(job1)

        # Modify one file
        (tmp_docs_folder / "intro.md").write_text(
            "# Completely Updated Introduction\n\nNew content.\n" * 10
        )

        mock_vector_store.add_chunks.reset_mock()

        svc2 = _make_svc(db, mock_vector_store, mock_embedding_service)
        job2 = await svc2.start_ingestion(str(tmp_docs_folder))
        await db.commit()
        await svc2.run_pipeline(job2)

        # add_chunks called for the modified file
        mock_vector_store.add_chunks.assert_called()

        result = await db.execute(
            select(IngestionJob).where(IngestionJob.id == job2.id)
        )
        job2_persisted = result.scalars().first()
        assert job2_persisted is not None
        assert job2_persisted.modified_files >= 1

    async def test_deleted_file_removed_from_db(
        self,
        db: AsyncSession,
        mock_vector_store: MagicMock,
        mock_embedding_service: EmbeddingService,
        tmp_docs_folder: Path,
    ) -> None:
        # First run — ingest both files
        svc = _make_svc(db, mock_vector_store, mock_embedding_service)
        job1 = await svc.start_ingestion(str(tmp_docs_folder))
        await db.commit()
        await svc.run_pipeline(job1)

        # Delete one file from disk
        (tmp_docs_folder / "concepts.md").unlink()

        # Second run
        svc2 = _make_svc(db, mock_vector_store, mock_embedding_service)
        job2 = await svc2.start_ingestion(str(tmp_docs_folder))
        await db.commit()
        await svc2.run_pipeline(job2)

        result = await db.execute(select(Document))
        remaining = result.scalars().all()
        file_names = {d.file_name for d in remaining}
        assert "concepts.md" not in file_names
        mock_vector_store.delete_by_document_id.assert_called()


class TestIngestionGuardRails:
    """Guard-rail enforcement: conflicts, path validation."""

    async def test_invalid_path_raises_path_validation_error(
        self,
        db: AsyncSession,
        mock_vector_store: MagicMock,
        mock_embedding_service: EmbeddingService,
    ) -> None:
        from app.core.exceptions import PathValidationError

        svc = _make_svc(db, mock_vector_store, mock_embedding_service)
        with pytest.raises(PathValidationError):
            await svc.start_ingestion("/nonexistent/path/that/does/not/exist")

    async def test_single_job_enforcement(
        self,
        db: AsyncSession,
        mock_vector_store: MagicMock,
        mock_embedding_service: EmbeddingService,
        tmp_docs_folder: Path,
    ) -> None:
        from app.core.exceptions import IngestionConflictError

        # Start first job — don't run it (status stays "running")
        svc = _make_svc(db, mock_vector_store, mock_embedding_service)
        await svc.start_ingestion(str(tmp_docs_folder))
        await db.commit()

        # Second start_ingestion must raise IngestionConflictError (FR-022)
        svc2 = _make_svc(db, mock_vector_store, mock_embedding_service)
        with pytest.raises(IngestionConflictError):
            await svc2.start_ingestion(str(tmp_docs_folder))
