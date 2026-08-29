"""
Analysis API Router - Shelf Image Analysis Endpoints

This module implements FastAPI endpoints for submitting and retrieving shelf analysis jobs.
Supports Challenge 1 (Out-of-Stock Detection) with gap detection using YOLOv8.

Endpoints:
    POST /api/v1/analysis/detect-gaps - Submit image for out-of-stock detection
    GET  /api/v1/analysis/jobs/{job_id} - Get analysis job status and results

Architecture:
    Request → Validate image → Save to disk → Create job record →
    Background task → ML processing → Update job with results

Features:
    - Image upload validation (format, size limits)
    - Asynchronous ML processing (non-blocking API)
    - Database persistence (AnalysisJob + Detection tables)
    - Structured error handling with educational messages
    - Response schemas for type-safe JSON

Related:
    - Detector: src/shelf_monitor/core/detector.py
    - CRUD: src/shelf_monitor/database/crud.py
    - Schemas: src/shelf_monitor/database/schemas.py
    - Tasks: T034 (router), T036 (workflow), T037 (ML processing)
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from src.shelf_monitor.api.dependencies import get_db
from src.shelf_monitor.config.settings import settings
from src.shelf_monitor.database import crud
from src.shelf_monitor.database.schemas import AnalysisJobResponse
from src.shelf_monitor.utils.logging import get_logger

logger = get_logger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/api/v1/analysis",
    tags=["analysis"],
    responses={
        404: {"description": "Analysis job not found"},
        400: {"description": "Invalid request (bad image format or parameters)"},
    },
)

# Image validation constants
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE_MB = 10
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


# ============================================================================
# Helper Functions
# ============================================================================


def validate_image_file(file: UploadFile) -> None:
    """
    Validate uploaded image file.
    
    Checks:
        - File extension (.jpg, .jpeg, .png)
        - File size (< 10MB)
        - Content type (image/*)
    
    Args:
        file: Uploaded file from FastAPI
    
    Raises:
        HTTPException: If validation fails with 400 status
    
    Example:
        >>> validate_image_file(upload_file)
        # Raises HTTPException if invalid
    """
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid file format '{file_ext}'. "
                f"Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}. "
                f"Please upload a JPEG or PNG image."
            ),
        )
    
    # Check content type
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid content type '{file.content_type}'. "
                f"Expected image/* type. "
                f"Please upload a valid image file."
            ),
        )
    
    # Note: File size check happens during save to avoid loading entire file into memory
    logger.info(
        f"Image validation passed: {file.filename}",
        extra={"filename": file.filename, "content_type": file.content_type},
    )


def save_uploaded_image(file: UploadFile, upload_dir: Path) -> str:
    """
    Save uploaded image to disk with unique filename.
    
    Creates upload directory if it doesn't exist.
    Generates unique filename with timestamp to avoid collisions.
    
    Args:
        file: Uploaded file from FastAPI
        upload_dir: Directory to save images (e.g., data/uploads/)
    
    Returns:
        Relative path to saved image (e.g., "data/uploads/shelf_20240115_103045.jpg")
    
    Raises:
        HTTPException: If file is too large or save fails
    
    Example:
        >>> path = save_uploaded_image(file, Path("data/uploads"))
        >>> print(path)
        data/uploads/shelf_20240115_103045_abc123.jpg
    """
    # Create upload directory if it doesn't exist
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename: shelf_YYYYMMDD_HHMMSS_original.ext
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = Path(file.filename).suffix.lower()
    base_name = Path(file.filename).stem[:50]  # Limit base name length
    unique_filename = f"shelf_{timestamp}_{base_name}{file_ext}"
    
    file_path = upload_dir / unique_filename
    
    try:
        # Save file with size check
        bytes_written = 0
        with open(file_path, "wb") as buffer:
            for chunk in file.file:
                bytes_written += len(chunk)
                
                # Check size during write to avoid memory issues
                if bytes_written > MAX_FILE_SIZE_BYTES:
                    # Remove partial file
                    buffer.close()
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"File size exceeds {MAX_FILE_SIZE_MB}MB limit. "
                            f"Uploaded: {bytes_written / 1024 / 1024:.2f}MB. "
                            f"Please compress the image or use a smaller resolution."
                        ),
                    )
                
                buffer.write(chunk)
        
        logger.info(
            f"Image saved successfully: {unique_filename}",
            extra={
                "file_path": str(file_path),
                "size_mb": bytes_written / 1024 / 1024,
            },
        )
        
        # Return relative path from project root
        return str(file_path)
        
    except HTTPException:
        raise
    
    except Exception as e:
        # Clean up on error
        file_path.unlink(missing_ok=True)
        logger.error(
            f"Failed to save image: {str(e)}",
            extra={"filename": file.filename, "error_type": type(e).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded image: {str(e)}",
        )


def process_gap_detection_task(job_id: int, image_path: str, confidence_threshold: float) -> None:
    """
    Background task: Run ML gap detection and save results.
    
    This function runs asynchronously after the API returns a response.
    It performs the ML processing and updates the database with results.
    
    Steps:
        1. Update job status to PROCESSING
        2. Load ProductDetector with YOLO model
        3. Detect products in image
        4. Detect gaps between products
        5. Save Detection records to database
        6. Update job status to COMPLETED with summary
        7. Handle errors by updating job status to FAILED
    
    Args:
        job_id: Analysis job ID to update
        image_path: Path to uploaded image
        confidence_threshold: Minimum confidence for detections
    
    Example:
        >>> # Called automatically by BackgroundTasks
        >>> process_gap_detection_task(job_id=1, image_path="data/uploads/shelf.jpg", confidence_threshold=0.5)
    """
    from src.shelf_monitor.core.detector import ProductDetector
    from src.shelf_monitor.database.session import SessionLocal
    
    db = SessionLocal()
    
    try:
        # Update job status to PROCESSING
        crud.update_analysis_job(db, job_id=job_id, status="PROCESSING")
        logger.info(
            f"Starting gap detection for job {job_id}",
            extra={"job_id": job_id, "image_path": image_path},
        )
        
        # Initialize detector with YOLO model
        detector = ProductDetector(confidence_threshold=confidence_threshold)
        
        # Detect products
        detections = detector.detect_products(image_path)
        logger.info(
            f"Detected {len(detections)} products",
            extra={"job_id": job_id, "detection_count": len(detections)},
        )
        
        # Detect gaps (need image width for analysis)
        from PIL import Image
        with Image.open(image_path) as img:
            image_width = img.width
        
        gaps = detector.detect_gaps(detections, image_width=image_width)
        significant_gaps = [g for g in gaps if g.is_significant]
        
        logger.info(
            f"Detected {len(significant_gaps)} significant gaps",
            extra={
                "job_id": job_id,
                "total_gaps": len(gaps),
                "significant_gaps": len(significant_gaps),
            },
        )
        
        # Save detections to database
        for det in detections:
            crud.create_detection(
                db=db,
                analysis_job_id=job_id,
                bbox_x=det.bbox[0],
                bbox_y=det.bbox[1],
                bbox_width=det.bbox[2],
                bbox_height=det.bbox[3],
                confidence=det.confidence,
                label=det.label,
                product_id=det.product_id,
            )
        
        # Prepare result summary
        result_summary = {
            "total_products": len(detections),
            "gaps_detected": len(gaps),
            "significant_gaps": len(significant_gaps),
            "gap_regions": [
                {
                    "x": gap.bbox[0],
                    "y": gap.bbox[1],
                    "width": gap.bbox[2],
                    "height": gap.bbox[3],
                    "gap_width": gap.gap_width,
                    "is_significant": gap.is_significant,
                }
                for gap in significant_gaps
            ],
        }
        
        # Update job status to COMPLETED
        crud.update_analysis_job(
            db=db,
            job_id=job_id,
            status="COMPLETED",
            result_summary=result_summary,
            completed_at=datetime.now(),
        )
        
        logger.info(
            f"Gap detection completed for job {job_id}",
            extra={"job_id": job_id, "result_summary": result_summary},
        )
        
    except Exception as e:
        # Update job status to FAILED with error message
        error_message = f"{type(e).__name__}: {str(e)}"
        crud.update_analysis_job(
            db=db,
            job_id=job_id,
            status="FAILED",
            error_message=error_message,
            completed_at=datetime.now(),
        )
        
        logger.error(
            f"Gap detection failed for job {job_id}: {error_message}",
            extra={"job_id": job_id, "error_type": type(e).__name__},
        )
    
    finally:
        db.close()


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/detect-gaps",
    response_model=AnalysisJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit image for out-of-stock detection",
    description="Upload shelf image and detect gaps (empty spaces) between products",
)
async def detect_gaps(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(..., description="Shelf image file (JPEG or PNG, max 10MB)"),
    confidence_threshold: float = Form(
        0.5,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence (0.0-1.0, default: 0.5)",
    ),
    db: Session = Depends(get_db),
) -> AnalysisJobResponse:
    """
    Submit shelf image for out-of-stock detection (Challenge 1).
    
    This endpoint accepts an uploaded image, saves it to disk, creates an analysis job,
    and queues ML processing in the background. The API returns immediately with job details.
    
    **Request** (multipart/form-data):
    - `image`: Image file (JPEG or PNG, max 10MB)
    - `confidence_threshold`: Minimum confidence for detections (0.0-1.0, default: 0.5)
    
    **Response** (201 Created):
    ```json
    {
        "id": 1,
        "image_path": "data/uploads/shelf_20240115_103045.jpg",
        "challenge_type": "OUT_OF_STOCK",
        "status": "PENDING",
        "result_summary": null,
        "error_message": null,
        "created_at": "2024-01-15T10:30:45",
        "completed_at": null
    }
    ```
    
    **Processing Flow**:
    1. Validate image (format, size)
    2. Save image to `data/uploads/` directory
    3. Create AnalysisJob record (status=PENDING)
    4. Queue background ML processing task
    5. Return job details immediately
    6. Background: Detect products → Detect gaps → Save to DB → Update job status
    
    **Status Progression**:
    - `PENDING`: Job created, queued for processing
    - `PROCESSING`: ML model running
    - `COMPLETED`: Results available (check `result_summary`)
    - `FAILED`: Error occurred (check `error_message`)
    
    **Errors**:
    - `400 Bad Request`: Invalid image format, size, or parameters
    - `500 Internal Server Error`: Server-side processing error
    
    **Example Usage**:
    ```python
    import httpx
    
    with open("shelf.jpg", "rb") as f:
        response = httpx.post(
            "http://localhost:8000/api/v1/analysis/detect-gaps",
            files={"image": ("shelf.jpg", f, "image/jpeg")},
            data={"confidence_threshold": 0.7}
        )
    
    job = response.json()
    print(f"Job ID: {job['id']}, Status: {job['status']}")
    
    # Poll for results
    job_id = job['id']
    result = httpx.get(f"http://localhost:8000/api/v1/analysis/jobs/{job_id}")
    print(result.json()["result_summary"])
    ```
    
    **Performance**:
    - Image upload + job creation: ~50-100ms
    - ML processing (background): ~300-500ms for 1920x1080 image
    - Total time to results: ~500-600ms
    
    Args:
        background_tasks: FastAPI background task handler
        image: Uploaded image file
        confidence_threshold: Minimum confidence score for detections
        db: Database session (injected dependency)
    
    Returns:
        AnalysisJobResponse with job details (status=PENDING initially)
    
    Raises:
        HTTPException: 400 for invalid inputs, 500 for server errors
    """
    logger.info(
        "Received gap detection request",
        extra={
            "filename": image.filename,
            "content_type": image.content_type,
            "confidence_threshold": confidence_threshold,
        },
    )
    
    # Validate image file
    validate_image_file(image)
    
    # Validate confidence threshold (already validated by Form, but double-check)
    if not (0.0 <= confidence_threshold <= 1.0):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Confidence threshold must be between 0.0 and 1.0, got {confidence_threshold}. "
                f"Use 0.5 for balanced results, or adjust based on your precision/recall needs."
            ),
        )
    
    # Save uploaded image
    upload_dir = Path("data/uploads")
    image_path = save_uploaded_image(image, upload_dir)
    
    # Create analysis job in database
    try:
        job = crud.create_analysis_job(
            db=db,
            image_path=image_path,
            challenge_type="OUT_OF_STOCK",
        )
        
        logger.info(
            f"Created analysis job {job.id}",
            extra={"job_id": job.id, "image_path": image_path},
        )
        
    except Exception as e:
        # Clean up uploaded image on error
        Path(image_path).unlink(missing_ok=True)
        logger.error(
            f"Failed to create analysis job: {str(e)}",
            extra={"error_type": type(e).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create analysis job: {str(e)}",
        )
    
    # Queue background ML processing task
    background_tasks.add_task(
        process_gap_detection_task,
        job_id=job.id,
        image_path=image_path,
        confidence_threshold=confidence_threshold,
    )
    
    logger.info(
        f"Queued background processing for job {job.id}",
        extra={"job_id": job.id},
    )
    
    # Return job details immediately (status=PENDING)
    return AnalysisJobResponse.model_validate(job)


@router.get(
    "/jobs/{job_id}",
    response_model=AnalysisJobResponse,
    summary="Get analysis job status and results",
    description="Retrieve analysis job details, including processing status and ML results",
)
async def get_analysis_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> AnalysisJobResponse:
    """
    Get analysis job by ID.
    
    Retrieves the status and results of a previously submitted analysis job.
    Use this endpoint to poll for results after submitting an image.
    
    **Response** (200 OK):
    ```json
    {
        "id": 1,
        "image_path": "data/uploads/shelf_20240115_103045.jpg",
        "challenge_type": "OUT_OF_STOCK",
        "status": "COMPLETED",
        "result_summary": {
            "total_products": 45,
            "gaps_detected": 5,
            "significant_gaps": 3,
            "gap_regions": [
                {"x": 120, "y": 50, "width": 150, "height": 200, "gap_width": 150, "is_significant": true}
            ]
        },
        "error_message": null,
        "created_at": "2024-01-15T10:30:45",
        "completed_at": "2024-01-15T10:31:12"
    }
    ```
    
    **Status Values**:
    - `PENDING`: Job queued, not started yet
    - `PROCESSING`: ML model currently running
    - `COMPLETED`: Processing finished, check `result_summary` for results
    - `FAILED`: Error occurred, check `error_message` for details
    
    **Result Summary Structure** (when status=COMPLETED):
    - `total_products`: Number of products detected
    - `gaps_detected`: Total gaps found (including small ones)
    - `significant_gaps`: Gaps wider than threshold (default: 100px)
    - `gap_regions`: Array of gap bounding boxes with coordinates
    
    **Errors**:
    - `404 Not Found`: Job ID doesn't exist
    
    **Example Usage**:
    ```python
    import httpx
    import time
    
    # Submit job
    response = httpx.post("http://localhost:8000/api/v1/analysis/detect-gaps", ...)
    job_id = response.json()["id"]
    
    # Poll for results
    while True:
        result = httpx.get(f"http://localhost:8000/api/v1/analysis/jobs/{job_id}")
        job = result.json()
        
        if job["status"] == "COMPLETED":
            print(f"Found {job['result_summary']['significant_gaps']} gaps!")
            break
        elif job["status"] == "FAILED":
            print(f"Error: {job['error_message']}")
            break
        
        time.sleep(0.5)  # Wait 500ms before next poll
    ```
    
    Args:
        job_id: Analysis job identifier
        db: Database session (injected dependency)
    
    Returns:
        AnalysisJobResponse with job details and results
    
    Raises:
        HTTPException: 404 if job not found
    """
    logger.info(
        f"Retrieving analysis job {job_id}",
        extra={"job_id": job_id},
    )
    
    # Query database for job
    job = crud.get_analysis_job(db, job_id=job_id)
    
    if not job:
        logger.warning(
            f"Analysis job {job_id} not found",
            extra={"job_id": job_id},
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis job with ID {job_id} not found. Please check the job ID.",
        )
    
    logger.info(
        f"Retrieved analysis job {job_id}",
        extra={"job_id": job_id, "status": job.status},
    )
    
    return AnalysisJobResponse.model_validate(job)
