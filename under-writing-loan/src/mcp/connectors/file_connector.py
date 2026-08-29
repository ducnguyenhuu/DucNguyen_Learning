"""
File connector for MCP server - handles secure file access.

Provides abstracted access to uploaded loan application documents
with path validation to prevent directory traversal attacks.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple

from ..config import UPLOAD_DIR

logger = logging.getLogger(__name__)


class FileConnector:
    """
    Secure file access connector for loan application documents.
    
    Validates all file paths to ensure they stay within the allowed
    upload directory, preventing path traversal attacks.
    
    Usage:
        connector = FileConnector()
        content, content_type = connector.get_file("app-001/paystub.pdf")
    """
    
    def __init__(self, base_directory: Optional[Path] = None):
        """
        Initialize file connector.
        
        Args:
            base_directory: Root directory for file access (defaults to UPLOAD_DIR from config)
        """
        self.base_directory = base_directory or UPLOAD_DIR
        self.base_directory = Path(self.base_directory).resolve()
        
        # Ensure base directory exists
        self.base_directory.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"FileConnector initialized with base directory: {self.base_directory}")
    
    def get_file(self, filename: str) -> Tuple[bytes, str]:
        """
        Retrieve file content with security validation.
        
        Args:
            filename: Relative file path (e.g., "app-001/paystub.pdf")
        
        Returns:
            Tuple of (file_content, content_type)
        
        Raises:
            FileNotFoundError: File does not exist
            PermissionError: File path attempts directory traversal
            ValueError: Invalid file path
        
        Examples:
            >>> connector = FileConnector()
            >>> content, content_type = connector.get_file("app-001/paystub.pdf")
            >>> print(f"Content type: {content_type}, Size: {len(content)} bytes")
        """
        # Validate input
        if not filename or filename.strip() == "":
            raise ValueError("Filename cannot be empty")
        
        # Remove any leading/trailing whitespace
        filename = filename.strip()
        
        # Construct full path
        file_path = (self.base_directory / filename).resolve()
        
        # Security check: ensure resolved path is within base directory
        try:
            file_path.relative_to(self.base_directory)
        except ValueError:
            logger.warning(f"Path traversal attempt detected: {filename}")
            raise PermissionError(
                f"Access denied: Cannot access files outside {self.base_directory}"
            )
        
        # Check if file exists
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            raise FileNotFoundError(f"File not found: {filename}")
        
        # Check if it's actually a file (not a directory)
        if not file_path.is_file():
            logger.warning(f"Path is not a file: {file_path}")
            raise ValueError(f"Path is not a file: {filename}")
        
        # Determine content type based on file extension
        content_type = self._get_content_type(file_path)
        
        # Read file content
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            
            logger.info(
                f"Successfully read file: {filename} "
                f"(size: {len(content)} bytes, type: {content_type})"
            )
            
            return content, content_type
        
        except Exception as e:
            logger.error(f"Error reading file {filename}: {e}")
            raise IOError(f"Failed to read file: {filename}") from e
    
    def file_exists(self, filename: str) -> bool:
        """
        Check if a file exists without reading its content.
        
        Args:
            filename: Relative file path
        
        Returns:
            True if file exists and is accessible, False otherwise
        """
        try:
            file_path = (self.base_directory / filename).resolve()
            file_path.relative_to(self.base_directory)
            return file_path.exists() and file_path.is_file()
        except (ValueError, Exception):
            return False
    
    def list_files(self, subdirectory: str = "") -> list[str]:
        """
        List all files in a subdirectory (non-recursive).
        
        Args:
            subdirectory: Optional subdirectory to list (e.g., "app-001")
        
        Returns:
            List of relative file paths
        
        Raises:
            PermissionError: Subdirectory path attempts traversal
        """
        # Construct subdirectory path
        if subdirectory:
            search_path = (self.base_directory / subdirectory).resolve()
            
            # Security check
            try:
                search_path.relative_to(self.base_directory)
            except ValueError:
                raise PermissionError(
                    f"Access denied: Cannot access directories outside {self.base_directory}"
                )
        else:
            search_path = self.base_directory
        
        # Check if directory exists
        if not search_path.exists():
            return []
        
        if not search_path.is_dir():
            return []
        
        # List files (non-recursive)
        files = []
        for item in search_path.iterdir():
            if item.is_file():
                # Return relative path from base directory
                relative_path = item.relative_to(self.base_directory)
                files.append(str(relative_path))
        
        logger.info(f"Listed {len(files)} files in {subdirectory or 'root'}")
        return sorted(files)
    
    def _get_content_type(self, file_path: Path) -> str:
        """
        Determine MIME type based on file extension.
        
        Args:
            file_path: Path to the file
        
        Returns:
            MIME type string
        """
        extension = file_path.suffix.lower()
        
        content_types = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".txt": "text/plain",
            ".json": "application/json",
            ".xml": "application/xml",
            ".csv": "text/csv",
        }
        
        return content_types.get(extension, "application/octet-stream")
    
    def get_file_info(self, filename: str) -> dict:
        """
        Get file metadata without reading content.
        
        Args:
            filename: Relative file path
        
        Returns:
            Dictionary with file information (size, type, exists)
        
        Raises:
            PermissionError: File path attempts directory traversal
        """
        try:
            file_path = (self.base_directory / filename).resolve()
            file_path.relative_to(self.base_directory)
            
            if not file_path.exists():
                return {
                    "exists": False,
                    "filename": filename,
                    "size_bytes": None,
                    "content_type": None,
                }
            
            if not file_path.is_file():
                return {
                    "exists": False,
                    "filename": filename,
                    "size_bytes": None,
                    "content_type": None,
                    "error": "Path is not a file",
                }
            
            stat = file_path.stat()
            return {
                "exists": True,
                "filename": filename,
                "size_bytes": stat.st_size,
                "content_type": self._get_content_type(file_path),
                "modified_at": stat.st_mtime,
            }
        
        except ValueError:
            raise PermissionError(
                f"Access denied: Cannot access files outside {self.base_directory}"
            )
