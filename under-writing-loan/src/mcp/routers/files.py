"""
Files router - handles document file access.

Provides endpoints for retrieving uploaded loan application documents.
Implements security checks to prevent directory traversal attacks.
"""

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from ..config import UPLOAD_DIR
from ..models import ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/files/{filename:path}",
    responses={
        200: {"description": "File content returned successfully"},
        404: {"model": ErrorResponse, "description": "File not found"},
        403: {"model": ErrorResponse, "description": "Access denied"}
    },
    summary="Retrieve an uploaded document"
)
async def get_file(filename: str):
    """
    Retrieve uploaded loan application document.
    
    Security note: This endpoint prevents path traversal attacks by validating
    that the resolved file path stays within UPLOAD_DIR.
    
    Args:
        filename: Relative file path (e.g., "app-001/paystub.pdf")
    
    Returns:
        File content (binary)
    
    Raises:
        HTTPException 404: File not found
        HTTPException 403: Path traversal attempt detected
    """
    try:
        # Resolve the full path (handles .., ., symlinks)
        file_path = (UPLOAD_DIR / filename).resolve()
        
        # Security: Ensure resolved path is within UPLOAD_DIR
        if not str(file_path).startswith(str(UPLOAD_DIR.resolve())):
            logger.warning(f"Path traversal attempt detected: {filename}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Access denied",
                    "detail": f"Cannot access files outside {UPLOAD_DIR}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "File not found",
                    "detail": f"No file exists at {file_path}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        logger.info(f"Serving file: {file_path}")
        return FileResponse(
            path=file_path,
            media_type="application/octet-stream",
            filename=file_path.name
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving file {filename}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "detail": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
