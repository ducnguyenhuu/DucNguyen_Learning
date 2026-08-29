"""Service layer for Knowledge Base AI.

Each service encapsulates a single domain concern and accepts its
dependencies (providers, DB sessions) via constructor injection.
"""

from app.services.embedding import EmbeddingResult, EmbeddingService
from app.services.ingestion import IngestionService, check_disk_space, compute_sha256, scan_folder, validate_folder_path

__all__ = [
    "EmbeddingResult",
    "EmbeddingService",
    "IngestionService",
    "check_disk_space",
    "compute_sha256",
    "scan_folder",
    "validate_folder_path",
]
