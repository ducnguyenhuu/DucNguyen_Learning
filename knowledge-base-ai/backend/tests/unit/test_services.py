"""Unit tests for backend service layer.

Coverage includes (per Constitution §VII):
- EmbeddingService: single embed, batch embed, model_version tagging, validation,
  error wrapping, property delegation.
- IngestionService helpers: validate_folder_path, check_disk_space, scan_folder,
  compute_sha256.
- IngestionService: single-job enforcement, start_ingestion pre-flight,
  run_pipeline (new/modified/deleted/unchanged/crash-resume detection).

Additional service tests (chat, retrieval, summary) will be added
here as the corresponding service modules are implemented (T037–T041).
"""
from __future__ import annotations

import pytest

from app.core.exceptions import AppError, ModelUnavailableError
from app.providers.base import EmbeddingProvider
from app.services.embedding import EmbeddingResult, EmbeddingService


# ---------------------------------------------------------------------------
# Mock provider helpers
# ---------------------------------------------------------------------------

DIM = 4  # small dimension for fast tests
_MODEL = "test-embed-v1"


class _StubEmbeddingProvider(EmbeddingProvider):
    """Minimal EmbeddingProvider that returns predictable fake vectors."""

    def __init__(
        self,
        model_version: str = _MODEL,
        dimensions: int = DIM,
        raise_on_embed: Exception | None = None,
    ) -> None:
        self._model_version = model_version
        self._dimensions = dimensions
        self._raise_on_embed = raise_on_embed

    async def embed(self, text: str) -> list[float]:
        if self._raise_on_embed is not None:
            raise self._raise_on_embed
        # vector length equals text length, clipped to DIM
        return [float(ord(c) % 10) for c in text[:self._dimensions]][:self._dimensions] + [0.0] * max(0, self._dimensions - len(text))

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if self._raise_on_embed is not None:
            raise self._raise_on_embed
        return [await self.embed(t) for t in texts]

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def dimensions(self) -> int:
        return self._dimensions


def _make_service(**kwargs: object) -> EmbeddingService:
    return EmbeddingService(_StubEmbeddingProvider(**kwargs))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# EmbeddingResult dataclass
# ---------------------------------------------------------------------------


class TestEmbeddingResult:
    def test_fields_stored(self) -> None:
        r = EmbeddingResult(vector=[1.0, 0.0], model_version="v1", text_length=5)
        assert r.vector == [1.0, 0.0]
        assert r.model_version == "v1"
        assert r.text_length == 5

    def test_frozen(self) -> None:
        r = EmbeddingResult(vector=[1.0], model_version="v1", text_length=1)
        with pytest.raises((AttributeError, TypeError)):
            r.model_version = "v2"  # type: ignore[misc]

    def test_equality(self) -> None:
        r1 = EmbeddingResult(vector=[1.0, 2.0], model_version="v1", text_length=3)
        r2 = EmbeddingResult(vector=[1.0, 2.0], model_version="v1", text_length=3)
        assert r1 == r2

    def test_inequality_different_vector(self) -> None:
        r1 = EmbeddingResult(vector=[1.0], model_version="v1", text_length=1)
        r2 = EmbeddingResult(vector=[2.0], model_version="v1", text_length=1)
        assert r1 != r2


# ---------------------------------------------------------------------------
# EmbeddingService construction
# ---------------------------------------------------------------------------


class TestEmbeddingServiceConstruction:
    def test_init_stores_provider(self) -> None:
        provider = _StubEmbeddingProvider()
        svc = EmbeddingService(provider)
        assert svc._provider is provider

    def test_model_version_delegates(self) -> None:
        svc = _make_service(model_version="custom-model-v2")
        assert svc.model_version == "custom-model-v2"

    def test_dimensions_delegates(self) -> None:
        svc = _make_service(dimensions=768)
        assert svc.dimensions == 768


# ---------------------------------------------------------------------------
# EmbeddingService.embed
# ---------------------------------------------------------------------------


class TestEmbeddingServiceEmbed:
    async def test_returns_embedding_result(self) -> None:
        svc = _make_service()
        result = await svc.embed("hello")
        assert isinstance(result, EmbeddingResult)

    async def test_vector_has_correct_dimensions(self) -> None:
        svc = _make_service(dimensions=DIM)
        result = await svc.embed("hi")
        assert len(result.vector) == DIM

    async def test_model_version_tagged(self) -> None:
        svc = _make_service(model_version="nomic-embed-text-v1.5")
        result = await svc.embed("some text")
        assert result.model_version == "nomic-embed-text-v1.5"

    async def test_text_length_recorded(self) -> None:
        svc = _make_service()
        text = "hello world"
        result = await svc.embed(text)
        assert result.text_length == len(text)

    async def test_empty_string_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="non-empty"):
            await svc.embed("")

    async def test_whitespace_only_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="non-empty"):
            await svc.embed("   ")

    async def test_app_error_re_raised_unchanged(self) -> None:
        """ModelUnavailableError (AppError subclass) must propagate as-is."""
        exc = ModelUnavailableError(model="test-model", reason="offline")
        svc = _make_service(raise_on_embed=exc)
        with pytest.raises(ModelUnavailableError):
            await svc.embed("test")

    async def test_generic_exception_wrapped_as_app_error(self) -> None:
        svc = _make_service(raise_on_embed=RuntimeError("crash"))
        with pytest.raises(AppError, match="Embedding failed"):
            await svc.embed("test")

    async def test_vector_elements_are_floats(self) -> None:
        svc = _make_service()
        result = await svc.embed("abc")
        assert all(isinstance(v, float) for v in result.vector)


# ---------------------------------------------------------------------------
# EmbeddingService.embed_batch
# ---------------------------------------------------------------------------


class TestEmbeddingServiceEmbedBatch:
    async def test_returns_list_of_embedding_results(self) -> None:
        svc = _make_service()
        results = await svc.embed_batch(["foo", "bar", "baz"])
        assert len(results) == 3
        assert all(isinstance(r, EmbeddingResult) for r in results)

    async def test_order_preserved(self) -> None:
        """Each result's text_length must correspond to its input."""
        svc = _make_service()
        texts = ["a", "hello", "world!"]
        results = await svc.embed_batch(texts)
        for r, t in zip(results, texts):
            assert r.text_length == len(t)

    async def test_all_tagged_with_same_model_version(self) -> None:
        svc = _make_service(model_version="model-x")
        results = await svc.embed_batch(["alpha", "beta"])
        assert all(r.model_version == "model-x" for r in results)

    async def test_empty_list_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="must not be empty"):
            await svc.embed_batch([])

    async def test_element_empty_string_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="texts\\[1\\]"):
            await svc.embed_batch(["valid", ""])

    async def test_element_whitespace_only_raises_value_error(self) -> None:
        svc = _make_service()
        with pytest.raises(ValueError, match="texts\\[0\\]"):
            await svc.embed_batch(["   ", "valid"])

    async def test_app_error_re_raised_unchanged(self) -> None:
        exc = ModelUnavailableError(model="x", reason="down")
        svc = _make_service(raise_on_embed=exc)
        with pytest.raises(ModelUnavailableError):
            await svc.embed_batch(["text"])

    async def test_generic_exception_wrapped_as_app_error(self) -> None:
        svc = _make_service(raise_on_embed=OSError("io"))
        with pytest.raises(AppError, match="Batch embedding failed"):
            await svc.embed_batch(["text"])

    async def test_single_text_batch(self) -> None:
        svc = _make_service()
        results = await svc.embed_batch(["only one"])
        assert len(results) == 1
        assert results[0].text_length == len("only one")

    async def test_vectors_have_correct_dimension(self) -> None:
        svc = _make_service(dimensions=DIM)
        results = await svc.embed_batch(["a", "b"])
        assert all(len(r.vector) == DIM for r in results)


# ===========================================================================
# Ingestion service — helper functions (pure / near-pure, no DB needed)
# ===========================================================================

import hashlib
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import IngestionConflictError, PathValidationError
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.services.ingestion import (
    IngestionService,
    _ScannedFile,
    check_disk_space,
    compute_sha256,
    scan_folder,
    validate_folder_path,
)


# ---------------------------------------------------------------------------
# validate_folder_path
# ---------------------------------------------------------------------------


class TestValidateFolderPath:
    def test_empty_string_raises(self) -> None:
        with pytest.raises(PathValidationError, match="must not be empty"):
            validate_folder_path("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(PathValidationError, match="must not be empty"):
            validate_folder_path("   ")

    def test_nonexistent_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PathValidationError, match="does not exist"):
            validate_folder_path(str(tmp_path / "ghost"))

    def test_file_path_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("hello")
        with pytest.raises(PathValidationError, match="not a directory"):
            validate_folder_path(str(f))

    def test_valid_directory_returns_resolved(self, tmp_path: Path) -> None:
        result = validate_folder_path(str(tmp_path))
        assert result == str(tmp_path.resolve())

    def test_symlink_resolved(self, tmp_path: Path) -> None:
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real_dir)
        result = validate_folder_path(str(link))
        assert result == str(real_dir.resolve())


# ---------------------------------------------------------------------------
# check_disk_space
# ---------------------------------------------------------------------------


class TestCheckDiskSpace:
    def test_enough_space_does_not_raise(self, tmp_path: Path) -> None:
        # Require 1 MB — virtually always available
        check_disk_space(str(tmp_path), min_mb=1)

    def test_insufficient_space_raises_app_error(self, tmp_path: Path) -> None:
        from app.core.exceptions import AppError

        # Require an absurdly large amount to guarantee failure
        with pytest.raises(AppError, match="Insufficient disk space"):
            check_disk_space(str(tmp_path), min_mb=999_999_999)

    def test_insufficient_space_raises_400(self, tmp_path: Path) -> None:
        from app.core.exceptions import AppError

        with pytest.raises(AppError) as exc_info:
            check_disk_space(str(tmp_path), min_mb=999_999_999)
        assert exc_info.value.status_code == 400

    def test_oserror_is_non_fatal(self, tmp_path: Path) -> None:
        """If disk_usage raises OSError, check_disk_space should not raise."""
        with patch("shutil.disk_usage", side_effect=OSError("no device")):
            check_disk_space(str(tmp_path), min_mb=500)  # must NOT raise


# ---------------------------------------------------------------------------
# compute_sha256
# ---------------------------------------------------------------------------


class TestComputeSha256:
    def test_returns_64_char_hex(self, tmp_path: Path) -> None:
        f = tmp_path / "a.txt"
        f.write_bytes(b"hello")
        digest = compute_sha256(str(f))
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_deterministic(self, tmp_path: Path) -> None:
        f = tmp_path / "b.txt"
        f.write_bytes(b"constant content")
        assert compute_sha256(str(f)) == compute_sha256(str(f))

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "c1.txt"
        f2 = tmp_path / "c2.txt"
        f1.write_bytes(b"aaa")
        f2.write_bytes(b"bbb")
        assert compute_sha256(str(f1)) != compute_sha256(str(f2))

    def test_matches_stdlib(self, tmp_path: Path) -> None:
        content = b"test content for sha256"
        f = tmp_path / "d.txt"
        f.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert compute_sha256(str(f)) == expected


# ---------------------------------------------------------------------------
# scan_folder
# ---------------------------------------------------------------------------


class TestScanFolder:
    def test_empty_folder_returns_empty(self, tmp_path: Path) -> None:
        assert scan_folder(str(tmp_path)) == []

    def test_returns_supported_files(self, tmp_path: Path) -> None:
        (tmp_path / "doc.pdf").write_bytes(b"%PDF")
        (tmp_path / "note.md").write_text("# Hello")
        results = scan_folder(str(tmp_path))
        names = {r.file_name for r in results}
        assert "doc.pdf" in names
        assert "note.md" in names

    def test_skips_unsupported_extensions(self, tmp_path: Path) -> None:
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        (tmp_path / "data.csv").write_text("a,b,c")
        (tmp_path / "doc.pdf").write_bytes(b"%PDF")
        results = scan_folder(str(tmp_path))
        names = {r.file_name for r in results}
        assert "image.png" not in names
        assert "data.csv" not in names
        assert "doc.pdf" in names

    def test_scans_subdirectories(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.md").write_text("# Nested")
        results = scan_folder(str(tmp_path))
        names = {r.file_name for r in results}
        assert "nested.md" in names

    def test_result_has_correct_extension(self, tmp_path: Path) -> None:
        (tmp_path / "doc.docx").write_bytes(b"PK\x03\x04")
        results = scan_folder(str(tmp_path))
        assert results[0].extension == ".docx"

    def test_result_has_file_hash(self, tmp_path: Path) -> None:
        f = tmp_path / "note.md"
        f.write_text("content")
        results = scan_folder(str(tmp_path))
        assert len(results[0].file_hash) == 64

    def test_result_has_file_size(self, tmp_path: Path) -> None:
        f = tmp_path / "small.md"
        f.write_bytes(b"abc")
        results = scan_folder(str(tmp_path))
        assert results[0].file_size_bytes == 3

    def test_xlsx_included(self, tmp_path: Path) -> None:
        (tmp_path / "sheet.xlsx").write_bytes(b"PK\x03\x04")
        results = scan_folder(str(tmp_path))
        assert any(r.extension == ".xlsx" for r in results)


# ---------------------------------------------------------------------------
# IngestionService (mocked DB + dependencies)
# ---------------------------------------------------------------------------


def _make_ingestion_service(
    *,
    running_job: IngestionJob | None = None,
    existing_docs: list[Document] | None = None,
    min_disk_space_mb: int = 1,
) -> tuple[IngestionService, AsyncMock, MagicMock, MagicMock]:
    """Return (service, mock_db, mock_vector_store, mock_embed_service)."""
    db = AsyncMock()

    # Simulate db.execute returning a scalars().all() result
    scalar_result = MagicMock()
    scalar_result.scalars.return_value.first.return_value = running_job
    scalar_result.scalars.return_value.all.return_value = existing_docs or []
    db.execute = AsyncMock(return_value=scalar_result)
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()

    vector_store = MagicMock()
    vector_store.delete_by_document_id = AsyncMock()
    vector_store.add_chunks = AsyncMock()

    embed_svc = MagicMock()
    embed_svc.embed_batch = AsyncMock(return_value=[])

    chunker = MagicMock()
    chunker.chunk = MagicMock(return_value=[])

    svc = IngestionService(
        db=db,
        vector_store=vector_store,
        embedding_service=embed_svc,
        chunker=chunker,
        min_disk_space_mb=min_disk_space_mb,
    )
    return svc, db, vector_store, embed_svc


class TestIngestionServiceConflictCheck:
    async def test_no_running_job_passes(self, tmp_path: Path) -> None:
        svc, *_ = _make_ingestion_service(running_job=None)
        # Should not raise — creates job
        job = await svc.start_ingestion(str(tmp_path))
        assert job.status == "running"

    async def test_running_job_raises_conflict(self, tmp_path: Path) -> None:
        running = IngestionJob(
            id="existing-job",
            source_folder=str(tmp_path),
            trigger_reason="user",
            status="running",
        )
        from datetime import UTC, datetime
        running.started_at = datetime.now(UTC)
        svc, *_ = _make_ingestion_service(running_job=running)
        with pytest.raises(IngestionConflictError):
            await svc.start_ingestion(str(tmp_path))


class TestIngestionServiceStartIngestion:
    async def test_invalid_path_raises_path_validation_error(self) -> None:
        svc, *_ = _make_ingestion_service(running_job=None)
        with pytest.raises(PathValidationError):
            await svc.start_ingestion("/nonexistent/ghost/folder")

    async def test_returns_running_job(self, tmp_path: Path) -> None:
        svc, db, *_ = _make_ingestion_service(running_job=None)
        job = await svc.start_ingestion(str(tmp_path))
        assert job.status == "running"
        assert job.source_folder == str(tmp_path.resolve())
        db.add.assert_called_once_with(job)
        db.flush.assert_called()

    async def test_trigger_reason_stored(self, tmp_path: Path) -> None:
        svc, *_ = _make_ingestion_service(running_job=None)
        job = await svc.start_ingestion(str(tmp_path), trigger_reason="reembed")
        assert job.trigger_reason == "reembed"

    async def test_low_disk_space_raises(self, tmp_path: Path) -> None:
        from app.core.exceptions import AppError

        svc, *_ = _make_ingestion_service(running_job=None, min_disk_space_mb=999_999_999)
        with pytest.raises(AppError, match="Insufficient disk space"):
            await svc.start_ingestion(str(tmp_path))


class TestIngestionPipelineFileDetection:
    """Tests for new / modified / deleted / unchanged detection in run_pipeline."""

    def _make_doc(
        self,
        *,
        file_path: str,
        file_hash: str = "aaa",
        status: str = "completed",
        tmp_path: Path | None = None,
    ) -> Document:
        from datetime import UTC, datetime

        d = Document(
            file_path=file_path,
            file_name=Path(file_path).name,
            file_type="md",
            file_hash=file_hash,
            file_size_bytes=10,
            status=status,
        )
        d.ingested_at = datetime.now(UTC)
        return d

    async def test_new_file_is_added_to_db(self, tmp_path: Path) -> None:
        (tmp_path / "new.md").write_text("# Hello")

        db = AsyncMock()
        scalar_result = MagicMock()
        # First call: check no running job → None; second call: load existing docs → []
        scalar_result.scalars.return_value.first.return_value = None
        scalar_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=scalar_result)
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.delete = AsyncMock()

        vector_store = MagicMock()
        vector_store.delete_by_document_id = AsyncMock()
        vector_store.add_chunks = AsyncMock()

        from app.services.embedding import EmbeddingResult

        embed_svc = MagicMock()
        embed_svc.embed_batch = AsyncMock(return_value=[
            EmbeddingResult(vector=[0.1, 0.2], model_version="v1", text_length=5)
        ])

        from app.parsers import Chunker, TextChunk

        chunker = MagicMock()
        fake_chunk = MagicMock(spec=TextChunk)
        fake_chunk.text = "Hello"
        fake_chunk.chunk_index = 0
        fake_chunk.page_number = None
        chunker.chunk = MagicMock(return_value=[fake_chunk])

        svc = IngestionService(
            db=db,
            vector_store=vector_store,
            embedding_service=embed_svc,
            chunker=chunker,
            min_disk_space_mb=1,
        )

        job = IngestionJob(
            id="job-1",
            source_folder=str(tmp_path),
            trigger_reason="user",
            status="running",
        )
        from datetime import UTC, datetime
        job.started_at = datetime.now(UTC)
        job.processed_files = 0
        job.new_files = 0
        job.modified_files = 0
        job.deleted_files = 0
        job.skipped_files = 0
        job.total_files = 0

        await svc.run_pipeline(job)

        # new Document was added to the session
        db.add.assert_called()
        # vectors were stored
        vector_store.add_chunks.assert_called_once()
        assert job.processed_files == 1
        assert job.status == "completed"

    async def test_deleted_file_removes_doc_and_vectors(self, tmp_path: Path) -> None:
        """A document in DB whose file_path is NOT on disk should be deleted."""
        ghost_path = str(tmp_path / "ghost.md")  # file does NOT exist on disk

        existing_doc = self._make_doc(file_path=ghost_path, file_hash="old")

        db = AsyncMock()
        scalar_result = MagicMock()
        scalar_result.scalars.return_value.first.return_value = None
        scalar_result.scalars.return_value.all.return_value = [existing_doc]
        db.execute = AsyncMock(return_value=scalar_result)
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.delete = AsyncMock()

        vector_store = MagicMock()
        vector_store.delete_by_document_id = AsyncMock()
        vector_store.add_chunks = AsyncMock()

        embed_svc = MagicMock()
        embed_svc.embed_batch = AsyncMock(return_value=[])

        chunker = MagicMock()
        chunker.chunk = MagicMock(return_value=[])

        svc = IngestionService(
            db=db,
            vector_store=vector_store,
            embedding_service=embed_svc,
            chunker=chunker,
            min_disk_space_mb=1,
        )

        job = IngestionJob(
            id="job-2",
            source_folder=str(tmp_path),
            trigger_reason="user",
            status="running",
        )
        from datetime import UTC, datetime
        job.started_at = datetime.now(UTC)
        job.processed_files = 0
        job.new_files = 0
        job.modified_files = 0
        job.deleted_files = 0
        job.skipped_files = 0
        job.total_files = 0

        await svc.run_pipeline(job)

        # ghost document was deleted from DB and its vectors removed
        db.delete.assert_called_once_with(existing_doc)
        vector_store.delete_by_document_id.assert_called_once_with(existing_doc.id)
        assert job.deleted_files == 1

    async def test_unchanged_file_skipped(self, tmp_path: Path) -> None:
        """A completed doc with matching hash must not be re-processed."""
        md_file = tmp_path / "same.md"
        md_file.write_text("# Same")
        real_hash = compute_sha256(str(md_file))

        existing_doc = self._make_doc(
            file_path=str(md_file.resolve()),
            file_hash=real_hash,
            status="completed",
        )

        db = AsyncMock()
        scalar_result = MagicMock()
        scalar_result.scalars.return_value.first.return_value = None
        scalar_result.scalars.return_value.all.return_value = [existing_doc]
        db.execute = AsyncMock(return_value=scalar_result)
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.delete = AsyncMock()

        vector_store = MagicMock()
        vector_store.delete_by_document_id = AsyncMock()
        vector_store.add_chunks = AsyncMock()

        embed_svc = MagicMock()
        embed_svc.embed_batch = AsyncMock(return_value=[])

        chunker = MagicMock()

        svc = IngestionService(
            db=db,
            vector_store=vector_store,
            embedding_service=embed_svc,
            chunker=chunker,
            min_disk_space_mb=1,
        )

        job = IngestionJob(
            id="job-3",
            source_folder=str(tmp_path),
            trigger_reason="user",
            status="running",
        )
        from datetime import UTC, datetime
        job.started_at = datetime.now(UTC)
        job.processed_files = 0
        job.new_files = 0
        job.modified_files = 0
        job.deleted_files = 0
        job.skipped_files = 0
        job.total_files = 0

        await svc.run_pipeline(job)

        # Nothing was added, deleted, or embedded
        db.add.assert_not_called()
        db.delete.assert_not_called()
        vector_store.add_chunks.assert_not_called()
        assert job.processed_files == 0
        assert job.total_files == 0

    async def test_crash_resume_reprocesses_processing_doc(self, tmp_path: Path) -> None:
        """A doc stuck in 'processing' (crash) must be re-processed."""
        md_file = tmp_path / "resume.md"
        md_file.write_text("# Resume")
        real_hash = compute_sha256(str(md_file))

        # Simulate doc left in processing state from a previous crash
        existing_doc = self._make_doc(
            file_path=str(md_file.resolve()),
            file_hash=real_hash,  # same hash, not modified — it's a resume
            status="processing",
        )

        db = AsyncMock()
        scalar_result = MagicMock()
        scalar_result.scalars.return_value.first.return_value = None
        scalar_result.scalars.return_value.all.return_value = [existing_doc]
        db.execute = AsyncMock(return_value=scalar_result)
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.delete = AsyncMock()

        vector_store = MagicMock()
        vector_store.delete_by_document_id = AsyncMock()
        vector_store.add_chunks = AsyncMock()

        from app.services.embedding import EmbeddingResult

        embed_svc = MagicMock()
        embed_svc.embed_batch = AsyncMock(return_value=[
            EmbeddingResult(vector=[0.1], model_version="v1", text_length=6)
        ])

        from app.parsers import Chunker, TextChunk

        chunker = MagicMock()
        fake_chunk = MagicMock(spec=TextChunk)
        fake_chunk.text = "Resume"
        fake_chunk.chunk_index = 0
        fake_chunk.page_number = None
        chunker.chunk = MagicMock(return_value=[fake_chunk])

        svc = IngestionService(
            db=db,
            vector_store=vector_store,
            embedding_service=embed_svc,
            chunker=chunker,
            min_disk_space_mb=1,
        )

        job = IngestionJob(
            id="job-4",
            source_folder=str(tmp_path),
            trigger_reason="user",
            status="running",
        )
        from datetime import UTC, datetime
        job.started_at = datetime.now(UTC)
        job.processed_files = 0
        job.new_files = 0
        job.modified_files = 0
        job.deleted_files = 0
        job.skipped_files = 0
        job.total_files = 0

        await svc.run_pipeline(job)

        # Old stale vectors deleted and new ones added
        vector_store.delete_by_document_id.assert_called_once()
        vector_store.add_chunks.assert_called_once()
        assert job.processed_files == 1
        assert existing_doc.status == "completed"


# ===========================================================================
# RetrievalService — T045
# ===========================================================================

from unittest.mock import AsyncMock, MagicMock

from app.db.vector_store import ChunkResult
from app.services.retrieval import RetrievalResult, RetrievalService, SourceReference


def _make_chunk_result(
    chunk_id: str = "doc1_0",
    document_id: str = "doc-1",
    file_name: str = "arch.pdf",
    file_path: str = "/docs/arch.pdf",
    text: str = "Chunk text about architecture.",
    chunk_index: int = 0,
    total_chunks: int = 5,
    page_number: int | None = 3,
    model_version: str = "nomic-embed-text-v1.5",
    distance: float = 0.08,  # → relevance_score = 0.92
) -> ChunkResult:
    return ChunkResult(
        chunk_id=chunk_id,
        document_id=document_id,
        file_name=file_name,
        file_path=file_path,
        text=text,
        chunk_index=chunk_index,
        total_chunks=total_chunks,
        page_number=page_number,
        model_version=model_version,
        distance=distance,
    )


def _make_retrieval_service(
    chunk_results: list[ChunkResult] | None = None,
    embed_raises: Exception | None = None,
) -> RetrievalService:
    """Build a RetrievalService with fully mocked dependencies."""
    provider = _StubEmbeddingProvider()
    if embed_raises is not None:
        provider = _StubEmbeddingProvider(raise_on_embed=embed_raises)

    vector_store = MagicMock(spec_set=["query"])
    vector_store.query = AsyncMock(return_value=chunk_results or [])

    return RetrievalService(embedding_provider=provider, vector_store=vector_store)


class TestSourceReference:
    def test_fields_stored(self) -> None:
        ref = SourceReference(
            document_id="d1",
            file_name="arch.pdf",
            page_number=5,
            relevance_score=0.91,
        )
        assert ref.document_id == "d1"
        assert ref.file_name == "arch.pdf"
        assert ref.page_number == 5
        assert ref.relevance_score == 0.91

    def test_to_dict_rounds_score(self) -> None:
        ref = SourceReference(
            document_id="d1",
            file_name="arch.pdf",
            page_number=None,
            relevance_score=0.91234567,
        )
        d = ref.to_dict()
        assert d["relevance_score"] == round(0.91234567, 4)
        assert d["page_number"] is None
        assert d["document_id"] == "d1"
        assert d["file_name"] == "arch.pdf"

    def test_frozen(self) -> None:
        ref = SourceReference("d1", "f.pdf", 1, 0.9)
        with pytest.raises(Exception):
            ref.document_id = "x"  # type: ignore[misc]


class TestRetrievalResult:
    def test_to_source_reference(self) -> None:
        result = RetrievalResult(
            chunk_id="doc1_0",
            document_id="doc-1",
            file_name="arch.pdf",
            file_path="/docs/arch.pdf",
            text="Some text",
            chunk_index=0,
            total_chunks=5,
            page_number=3,
            relevance_score=0.92,
            model_version="nomic-v1",
        )
        ref = result.to_source_reference()
        assert isinstance(ref, SourceReference)
        assert ref.document_id == "doc-1"
        assert ref.file_name == "arch.pdf"
        assert ref.page_number == 3
        assert ref.relevance_score == 0.92

    def test_to_source_reference_no_page(self) -> None:
        result = RetrievalResult(
            chunk_id="doc1_0",
            document_id="doc-1",
            file_name="notes.md",
            file_path="/docs/notes.md",
            text="Some text",
            chunk_index=0,
            total_chunks=2,
            page_number=None,
            relevance_score=0.85,
        )
        ref = result.to_source_reference()
        assert ref.page_number is None

    def test_frozen(self) -> None:
        result = RetrievalResult(
            chunk_id="x",
            document_id="y",
            file_name="f.md",
            file_path="/f.md",
            text="t",
            chunk_index=0,
            total_chunks=1,
            page_number=None,
            relevance_score=0.8,
        )
        with pytest.raises(Exception):
            result.relevance_score = 0.5  # type: ignore[misc]


class TestRetrievalService:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_results(self) -> None:
        svc = _make_retrieval_service(chunk_results=[])
        results = await svc.retrieve("What is the architecture?")
        assert results == []

    @pytest.mark.asyncio
    async def test_returns_retrieval_result_for_each_chunk(self) -> None:
        chunks = [
            _make_chunk_result(chunk_id="doc1_0", distance=0.08),  # score 0.92
            _make_chunk_result(chunk_id="doc1_1", chunk_index=1, distance=0.10),  # score 0.90
        ]
        svc = _make_retrieval_service(chunk_results=chunks)
        results = await svc.retrieve("architecture question")
        assert len(results) == 2
        assert all(isinstance(r, RetrievalResult) for r in results)

    @pytest.mark.asyncio
    async def test_results_sorted_by_relevance_descending(self) -> None:
        # Return lower-score first from vector store to verify re-sort
        chunks = [
            _make_chunk_result(chunk_id="doc1_1", chunk_index=1, distance=0.20),  # 0.80
            _make_chunk_result(chunk_id="doc1_0", chunk_index=0, distance=0.05),  # 0.95
        ]
        svc = _make_retrieval_service(chunk_results=chunks)
        results = await svc.retrieve("question")
        assert results[0].chunk_id == "doc1_0"
        assert results[1].chunk_id == "doc1_1"
        assert results[0].relevance_score > results[1].relevance_score

    @pytest.mark.asyncio
    async def test_chunk_result_fields_mapped_correctly(self) -> None:
        chunk = _make_chunk_result(
            chunk_id="doc1_2",
            document_id="doc-42",
            file_name="design.pdf",
            file_path="/docs/design.pdf",
            text="Service design principles.",
            chunk_index=2,
            total_chunks=10,
            page_number=7,
            model_version="nomic-v1.5",
            distance=0.06,  # relevance_score = 0.94
        )
        svc = _make_retrieval_service(chunk_results=[chunk])
        results = await svc.retrieve("design")
        r = results[0]
        assert r.chunk_id == "doc1_2"
        assert r.document_id == "doc-42"
        assert r.file_name == "design.pdf"
        assert r.file_path == "/docs/design.pdf"
        assert r.text == "Service design principles."
        assert r.chunk_index == 2
        assert r.total_chunks == 10
        assert r.page_number == 7
        assert r.model_version == "nomic-v1.5"
        assert abs(r.relevance_score - 0.94) < 0.001

    @pytest.mark.asyncio
    async def test_filters_chunks_below_threshold(self) -> None:
        # VectorStore already filters, but RetrievalService re-filters for safety
        chunks = [
            _make_chunk_result(chunk_id="ok", distance=0.08),    # score 0.92 ✓
            _make_chunk_result(chunk_id="low", distance=0.40),   # score 0.60 ✗
        ]
        svc = _make_retrieval_service(chunk_results=chunks)
        results = await svc.retrieve("question", similarity_threshold=0.70)
        assert len(results) == 1
        assert results[0].chunk_id == "ok"

    @pytest.mark.asyncio
    async def test_passes_top_k_to_vector_store(self) -> None:
        provider = _StubEmbeddingProvider()
        vector_store = MagicMock(spec_set=["query"])
        vector_store.query = AsyncMock(return_value=[])
        svc = RetrievalService(embedding_provider=provider, vector_store=vector_store)

        await svc.retrieve("query", top_k=3)

        vector_store.query.assert_called_once()
        call_kwargs = vector_store.query.call_args
        assert call_kwargs.kwargs.get("top_k") == 3

    @pytest.mark.asyncio
    async def test_passes_similarity_threshold_to_vector_store(self) -> None:
        provider = _StubEmbeddingProvider()
        vector_store = MagicMock(spec_set=["query"])
        vector_store.query = AsyncMock(return_value=[])
        svc = RetrievalService(embedding_provider=provider, vector_store=vector_store)

        await svc.retrieve("query", similarity_threshold=0.85)

        call_kwargs = vector_store.query.call_args
        assert call_kwargs.kwargs.get("similarity_threshold") == 0.85

    @pytest.mark.asyncio
    async def test_raises_app_error_on_empty_query(self) -> None:
        svc = _make_retrieval_service()
        with pytest.raises(AppError):
            await svc.retrieve("")

    @pytest.mark.asyncio
    async def test_raises_app_error_on_whitespace_query(self) -> None:
        svc = _make_retrieval_service()
        with pytest.raises(AppError):
            await svc.retrieve("   ")

    @pytest.mark.asyncio
    async def test_raises_app_error_when_embedding_fails(self) -> None:
        svc = _make_retrieval_service(embed_raises=RuntimeError("model down"))
        with pytest.raises(AppError, match="Failed to embed query"):
            await svc.retrieve("What is X?")

    @pytest.mark.asyncio
    async def test_embeds_query_before_calling_vector_store(self) -> None:
        """Verify embed() is called with the exact query text."""
        embed_calls: list[str] = []

        class _TrackingProvider(_StubEmbeddingProvider):
            async def embed(self, text: str) -> list[float]:
                embed_calls.append(text)
                return await super().embed(text)

        vector_store = MagicMock(spec_set=["query"])
        vector_store.query = AsyncMock(return_value=[])
        svc = RetrievalService(
            embedding_provider=_TrackingProvider(), vector_store=vector_store
        )
        await svc.retrieve("tell me about services")
        assert embed_calls == ["tell me about services"]

    @pytest.mark.asyncio
    async def test_query_text_stripped(self) -> None:
        """Leading/trailing whitespace in query is stripped before embedding."""
        embed_calls: list[str] = []

        class _TrackingProvider(_StubEmbeddingProvider):
            async def embed(self, text: str) -> list[float]:
                embed_calls.append(text)
                return await super().embed(text)

        vector_store = MagicMock(spec_set=["query"])
        vector_store.query = AsyncMock(return_value=[])
        svc = RetrievalService(
            embedding_provider=_TrackingProvider(), vector_store=vector_store
        )
        await svc.retrieve("  hello world  ")
        assert embed_calls == ["hello world"]

    @pytest.mark.asyncio
    async def test_to_source_reference_pipeline(self) -> None:
        """End-to-end: retrieve returns results whose to_source_reference() yields correct data."""
        chunk = _make_chunk_result(
            document_id="doc-99",
            file_name="spec.pdf",
            page_number=4,
            distance=0.07,  # score ≈ 0.93
        )
        svc = _make_retrieval_service(chunk_results=[chunk])
        results = await svc.retrieve("spec question")
        ref = results[0].to_source_reference()
        assert ref.document_id == "doc-99"
        assert ref.file_name == "spec.pdf"
        assert ref.page_number == 4
        assert ref.relevance_score > 0.9

# ===========================================================================
# T078 — ChatService unit tests
# ===========================================================================

from app.core.exceptions import ConversationNotFoundError
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.chat import (
    ChatService,
    _build_context_text,
    _build_prompt,
    _build_source_references,
    _NO_CONTEXT_NOTE,
)
from app.services.retrieval import RetrievalResult, SourceReference


def _make_retrieval_result(
    chunk_id: str = "c1",
    document_id: str = "doc-1",
    file_name: str = "arch.pdf",
    text: str = "Architecture overview.",
    page_number: int | None = 1,
    relevance_score: float = 0.9,
) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        document_id=document_id,
        file_name=file_name,
        file_path="/docs/arch.pdf",
        text=text,
        chunk_index=0,
        total_chunks=3,
        page_number=page_number,
        relevance_score=relevance_score,
        model_version="nomic-v1",
    )


class TestBuildContextText:
    """Tests for the module-level _build_context_text helper."""

    def test_empty_results_returns_no_context_note(self) -> None:
        assert _build_context_text([]) == _NO_CONTEXT_NOTE

    def test_single_result_formats_correctly(self) -> None:
        r = _make_retrieval_result(file_name="spec.pdf", text="Spec content.", page_number=2)
        output = _build_context_text([r])
        assert "[Source: spec.pdf, page 2]" in output
        assert "Spec content." in output

    def test_multiple_results_separated(self) -> None:
        r1 = _make_retrieval_result(chunk_id="c1", text="First.")
        r2 = _make_retrieval_result(chunk_id="c2", text="Second.")
        output = _build_context_text([r1, r2])
        assert "First." in output
        assert "Second." in output

    def test_no_page_number_omits_page(self) -> None:
        r = _make_retrieval_result(file_name="notes.md", page_number=None)
        output = _build_context_text([r])
        assert "[Source: notes.md]" in output


class TestBuildPrompt:
    """Tests for the module-level _build_prompt helper."""

    def test_contains_user_question(self) -> None:
        p = _build_prompt("What is RAG?", "")
        assert "What is RAG?" in p

    def test_with_history_includes_history(self) -> None:
        p = _build_prompt("Q", "User: hi\nAssistant: hello")
        assert "User: hi" in p
        assert "Assistant: hello" in p

    def test_without_history_excludes_history_heading(self) -> None:
        p = _build_prompt("Q", "")
        assert "history" not in p.lower()

    def test_contains_system_prompt(self) -> None:
        p = _build_prompt("Q", "")
        assert len(p) > len("Q")


class TestBuildSourceReferences:
    """Tests for the module-level _build_source_references helper."""

    def test_empty_results_returns_empty(self) -> None:
        assert _build_source_references([]) == []

    def test_deduplicates_same_doc_same_page(self) -> None:
        r1 = _make_retrieval_result(chunk_id="c1", document_id="d1", page_number=1, relevance_score=0.8)
        r2 = _make_retrieval_result(chunk_id="c2", document_id="d1", page_number=1, relevance_score=0.85)
        refs = _build_source_references([r1, r2])
        assert len(refs) == 1
        # Keeps the higher score
        assert refs[0].relevance_score == pytest.approx(0.85)

    def test_different_pages_both_included(self) -> None:
        r1 = _make_retrieval_result(chunk_id="c1", document_id="d1", page_number=1)
        r2 = _make_retrieval_result(chunk_id="c2", document_id="d1", page_number=2)
        refs = _build_source_references([r1, r2])
        assert len(refs) == 2

    def test_sorted_by_descending_score(self) -> None:
        r1 = _make_retrieval_result(chunk_id="c1", relevance_score=0.7, page_number=1)
        r2 = _make_retrieval_result(chunk_id="c2", relevance_score=0.95, page_number=2)
        refs = _build_source_references([r1, r2])
        assert refs[0].relevance_score > refs[1].relevance_score


class TestChatService:
    """Tests for ChatService using mocked DB + LLM provider."""

    def _make_conversation(self, cid: str = "conv-1") -> Conversation:
        from datetime import UTC, datetime
        c = Conversation()
        c.id = cid
        c.title = None
        c.preview = None
        c.message_count = 0
        c.created_at = datetime.now(UTC)
        c.updated_at = datetime.now(UTC)
        return c

    def _make_chat_service(
        self,
        retrieval_results: list[RetrievalResult] | None = None,
        llm_response: str = "LLM reply",
    ) -> ChatService:
        retrieval_svc = MagicMock()
        retrieval_svc.retrieve = AsyncMock(return_value=retrieval_results or [])

        llm = MagicMock()
        llm.generate = AsyncMock(return_value=llm_response)

        return ChatService(retrieval_service=retrieval_svc, llm_provider=llm)

    def _make_db(self, conversation: Conversation | None = None) -> AsyncMock:
        db = AsyncMock()
        # Scalar results for DB queries
        conv_result = MagicMock()
        conv_result.scalar_one_or_none.return_value = conversation
        # Messages history
        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[conv_result, msg_result])
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()
        return db

    async def test_send_message_raises_conversation_not_found(self) -> None:
        svc = self._make_chat_service()
        db = self._make_db(conversation=None)
        with pytest.raises(ConversationNotFoundError):
            await svc.send_message(db, "missing-id", "hello")

    async def test_send_message_returns_message_pair(self) -> None:
        conv = self._make_conversation()
        svc = self._make_chat_service(llm_response="4")
        db = self._make_db(conversation=conv)
        user_msg, asst_msg = await svc.send_message(db, conv.id, "What is 2+2?")
        assert user_msg.role == "user"
        assert asst_msg.role == "assistant"
        assert asst_msg.content == "4"

    async def test_send_message_persists_both_messages(self) -> None:
        conv = self._make_conversation()
        svc = self._make_chat_service()
        db = self._make_db(conversation=conv)
        await svc.send_message(db, conv.id, "Q?")
        # db.add should be called at least twice (user msg + assistant msg)
        assert db.add.call_count >= 2

    async def test_send_message_calls_llm(self) -> None:
        conv = self._make_conversation()
        retrieval_svc = MagicMock()
        retrieval_svc.retrieve = AsyncMock(return_value=[])
        llm = MagicMock()
        llm.generate = AsyncMock(return_value="answer")
        svc = ChatService(retrieval_service=retrieval_svc, llm_provider=llm)
        db = self._make_db(conversation=conv)
        await svc.send_message(db, conv.id, "Q?")
        llm.generate.assert_called_once()

    async def test_send_message_no_results_falls_back_to_no_context(self) -> None:
        """When retrieval returns nothing, context note is passed to LLM."""
        conv = self._make_conversation()
        retrieval_svc = MagicMock()
        retrieval_svc.retrieve = AsyncMock(return_value=[])
        llm = MagicMock()
        llm.generate = AsyncMock(return_value="no info")
        svc = ChatService(retrieval_service=retrieval_svc, llm_provider=llm)
        db = self._make_db(conversation=conv)
        await svc.send_message(db, conv.id, "Where is Atlantis?")
        # The context passed to LLM should contain the no-context note
        call_kwargs = llm.generate.call_args
        context_arg = call_kwargs.kwargs.get("context", call_kwargs.args[1] if len(call_kwargs.args) > 1 else "")
        assert _NO_CONTEXT_NOTE in context_arg

    async def test_send_message_source_refs_stored(self) -> None:
        """If retrieval returns results, assistant message has source refs."""
        conv = self._make_conversation()
        retrieval_result = _make_retrieval_result(document_id="doc-42", page_number=3, relevance_score=0.95)
        svc = self._make_chat_service(retrieval_results=[retrieval_result])
        db = self._make_db(conversation=conv)
        _, asst_msg = await svc.send_message(db, conv.id, "What?")
        assert asst_msg.source_references is not None
        assert len(asst_msg.source_references) == 1
        assert asst_msg.source_references[0]["document_id"] == "doc-42"

    async def test_build_history_text_formats_messages(self) -> None:
        """_build_history_text returns formatted conversation lines."""
        from datetime import UTC, datetime

        conv = self._make_conversation()
        svc = self._make_chat_service()

        # Build a db mock that returns 2 messages
        user_msg = Message()
        user_msg.id = "m1"
        user_msg.role = "user"
        user_msg.content = "Hello"
        user_msg.created_at = datetime.now(UTC)
        user_msg.conversation_id = conv.id
        user_msg.source_references = None

        asst_msg = Message()
        asst_msg.id = "m2"
        asst_msg.role = "assistant"
        asst_msg.content = "Hi there"
        asst_msg.created_at = datetime.now(UTC)
        asst_msg.conversation_id = conv.id
        asst_msg.source_references = None

        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [user_msg, asst_msg]
        db.execute = AsyncMock(return_value=result_mock)

        history = await svc._build_history_text(db, conv.id)

        assert "User: Hello" in history
        assert "Assistant: Hi there" in history

    async def test_build_history_text_empty_returns_empty_string(self) -> None:
        svc = self._make_chat_service()
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=result_mock)

        history = await svc._build_history_text(db, "conv-x")
        assert history == ""

    async def test_stream_message_yields_correct_event_types(self) -> None:
        """stream_message must yield UserMessageSaved, SourcesFound, Token(s), Complete."""
        from app.services.chat import (
            CompleteEvent,
            SourcesFoundEvent,
            TokenEvent,
            UserMessageSavedEvent,
        )

        conv = self._make_conversation()

        async def _fake_stream(prompt: str, context: str = "") -> Any:
            async def _gen() -> Any:
                yield "Hello"
                yield " world"
            return _gen()

        retrieval_svc = MagicMock()
        retrieval_svc.retrieve = AsyncMock(return_value=[])
        llm = MagicMock()
        llm.stream = _fake_stream

        svc = ChatService(retrieval_service=retrieval_svc, llm_provider=llm)

        db = AsyncMock()
        # First execute: load conversation; subsequent: message history
        conv_result = MagicMock()
        conv_result.scalar_one_or_none.return_value = conv
        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[conv_result, msg_result])
        db.add = MagicMock()
        db.flush = AsyncMock()
        db.commit = AsyncMock()

        events = []
        async for event in await svc.stream_message(db, conv.id, "Q?"):
            events.append(event)

        event_types = [type(e) for e in events]
        assert UserMessageSavedEvent in event_types
        assert SourcesFoundEvent in event_types
        assert TokenEvent in event_types
        assert CompleteEvent in event_types


# ===========================================================================
# T078 — SummaryService unit tests
# ===========================================================================

from app.db.vector_store import ChunkResult
from app.models.document import Document
from app.models.document_summary import DocumentSummary
from app.services.summary import SummaryGenerationError, SummaryService


def _make_chunk(
    chunk_id: str = "c1",
    document_id: str = "doc-1",
    text: str = "Chunk text.",
    chunk_index: int = 0,
    page_number: int | None = 1,
) -> ChunkResult:
    return ChunkResult(
        chunk_id=chunk_id,
        document_id=document_id,
        file_name="doc.pdf",
        file_path="/docs/doc.pdf",
        text=text,
        chunk_index=chunk_index,
        total_chunks=3,
        page_number=page_number,
        model_version="test-model",
        distance=0.1,
    )


def _make_document(doc_id: str = "doc-1") -> Document:
    from datetime import UTC, datetime
    d = Document(
        file_path=f"/docs/{doc_id}.pdf",
        file_name=f"{doc_id}.pdf",
        file_type="pdf",
        file_hash="abc123",
        file_size_bytes=1024,
        status="completed",
    )
    d.id = doc_id
    d.ingested_at = datetime.now(UTC)
    return d


def _make_summary_service(
    chunks: list[ChunkResult] | None = None,
    llm_response: str = "Summary text.",
) -> SummaryService:
    vector_store = MagicMock()
    vector_store.get_chunks_by_document_id = AsyncMock(return_value=chunks or [])

    llm = MagicMock()
    llm.generate = AsyncMock(return_value=llm_response)

    return SummaryService(vector_store=vector_store, llm_provider=llm, llm_model="test-llm")


class TestSummaryService:
    """Tests for SummaryService — uses mocked vector store and LLM provider."""

    def _make_db(self, existing_summary: DocumentSummary | None = None) -> AsyncMock:
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.first.return_value = existing_summary
        db.execute = AsyncMock(return_value=result)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    async def test_get_cached_returns_none_when_missing(self) -> None:
        svc = _make_summary_service()
        db = self._make_db(existing_summary=None)
        result = await svc.get_cached(db, "doc-99")
        assert result is None

    async def test_get_cached_returns_existing_summary(self) -> None:
        from datetime import UTC, datetime
        summary = DocumentSummary(
            document_id="doc-1",
            summary_text="Cached summary.",
            model_version="v1",
            created_at=datetime.now(UTC),
        )
        svc = _make_summary_service()
        db = self._make_db(existing_summary=summary)
        result = await svc.get_cached(db, "doc-1")
        assert result is summary

    async def test_get_or_generate_returns_cache_when_present(self) -> None:
        """get_or_generate(regenerate=False) should return cached summary without calling LLM."""
        from datetime import UTC, datetime
        existing = DocumentSummary(
            document_id="doc-1",
            summary_text="Cached.",
            model_version="v1",
            created_at=datetime.now(UTC),
        )
        vector_store = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock()
        svc = SummaryService(vector_store=vector_store, llm_provider=llm, llm_model="m")

        db = AsyncMock()
        cache_result = MagicMock()
        cache_result.scalars.return_value.first.return_value = existing
        db.execute = AsyncMock(return_value=cache_result)

        doc = _make_document("doc-1")
        result = await svc.get_or_generate(db, doc, regenerate=False)

        assert result is existing
        llm.generate.assert_not_called()

    async def test_get_or_generate_calls_llm_when_no_cache(self) -> None:
        doc = _make_document("doc-2")
        chunks = [_make_chunk(document_id="doc-2", text="Content text.")]
        svc = _make_summary_service(chunks=chunks, llm_response="Generated summary.")
        db = self._make_db(existing_summary=None)
        result = await svc.get_or_generate(db, doc)
        assert result is not None

    async def test_get_or_generate_regenerate_bypasses_cache(self) -> None:
        """regenerate=True should call LLM even when a cached summary exists."""
        from datetime import UTC, datetime
        existing = DocumentSummary(
            document_id="doc-3",
            summary_text="Old summary.",
            model_version="v0",
            created_at=datetime.now(UTC),
        )
        doc = _make_document("doc-3")
        chunks = [_make_chunk(document_id="doc-3", text="New content.")]
        llm = MagicMock()
        llm.generate = AsyncMock(return_value="Fresh summary.")
        vector_store = MagicMock()
        vector_store.get_chunks_by_document_id = AsyncMock(return_value=chunks)
        svc = SummaryService(vector_store=vector_store, llm_provider=llm, llm_model="m")

        db = AsyncMock()
        # Cache check returns existing, but regenerate=True should skip it
        cache_result = MagicMock()
        cache_result.scalars.return_value.first.return_value = existing
        db.execute = AsyncMock(return_value=cache_result)
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await svc.get_or_generate(db, doc, regenerate=True)
        llm.generate.assert_called()

    async def test_generate_raises_when_no_chunks(self) -> None:
        doc = _make_document("doc-empty")
        vector_store = MagicMock()
        vector_store.get_chunks_by_document_id = AsyncMock(return_value=[])
        llm = MagicMock()
        svc = SummaryService(vector_store=vector_store, llm_provider=llm, llm_model="m")
        db = AsyncMock()

        with pytest.raises(SummaryGenerationError):
            await svc._generate(db, doc)

    async def test_generate_single_batch_calls_llm_once(self) -> None:
        """A single chunk batch → LLM called once (no combiner needed)."""
        chunks = [_make_chunk(f"c{i}", text=f"Chunk {i}") for i in range(3)]
        doc = _make_document("doc-sb")
        vector_store = MagicMock()
        vector_store.get_chunks_by_document_id = AsyncMock(return_value=chunks)
        llm = MagicMock()
        llm.generate = AsyncMock(return_value="Single batch summary.")
        svc = SummaryService(vector_store=vector_store, llm_provider=llm, llm_model="m")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(**{"scalars.return_value.first.return_value": None}))
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await svc._generate(db, doc)
        # 3 chunks in one batch (_CHUNK_BATCH_SIZE=6) → one LLM call, no combiner
        assert llm.generate.call_count == 1

    async def test_generate_multi_batch_combines_summaries(self) -> None:
        """More than CHUNK_BATCH_SIZE chunks → LLM called N+1 times (one combiner call)."""
        _CHUNK_BATCH_SIZE = 6
        chunks = [_make_chunk(f"c{i}", text=f"Chunk {i}") for i in range(_CHUNK_BATCH_SIZE + 2)]
        doc = _make_document("doc-mb")
        vector_store = MagicMock()
        vector_store.get_chunks_by_document_id = AsyncMock(return_value=chunks)
        llm = MagicMock()
        llm.generate = AsyncMock(return_value="Partial summary.")
        svc = SummaryService(vector_store=vector_store, llm_provider=llm, llm_model="m")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock(**{"scalars.return_value.first.return_value": None}))
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        await svc._generate(db, doc)
        # 8 chunks → 2 batches → 2 partial + 1 combine = 3 calls
        assert llm.generate.call_count == 3

    async def test_build_section_refs_extracts_pages(self) -> None:
        chunks = [
            _make_chunk(f"c{i}", page_number=i + 1, text=f"Page {i+1} content.")
            for i in range(3)
        ]
        refs = SummaryService._build_section_refs(chunks)
        assert refs is not None
        assert len(refs) == 3
        page_numbers = [r["page"] for r in refs]
        assert page_numbers == [1, 2, 3]

    async def test_build_section_refs_none_when_no_pages(self) -> None:
        chunks = [_make_chunk("c1", page_number=None, text="No page.")]
        refs = SummaryService._build_section_refs(chunks)
        assert refs is None

    async def test_build_section_refs_deduplicates_pages(self) -> None:
        chunks = [
            _make_chunk("c1", page_number=1, text="First."),
            _make_chunk("c2", page_number=1, text="Also first."),
            _make_chunk("c3", page_number=2, text="Second."),
        ]
        refs = SummaryService._build_section_refs(chunks)
        assert refs is not None
        assert len(refs) == 2