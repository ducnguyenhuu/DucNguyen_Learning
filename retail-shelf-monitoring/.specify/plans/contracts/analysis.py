"""
Contract: Analysis API Router
Module: src/shelf_monitor/api/routers/analysis.py
Purpose: REST API endpoints for shelf image analysis (all 4 challenges)

This contract defines the FastAPI router for analysis operations:
- Submit shelf images for analysis
- Get analysis job status and results
- Support all 4 challenge types:
  1. OUT_OF_STOCK: Detect gaps in shelves
  2. PRODUCT_RECOGNITION: Identify SKUs
  3. STOCK_ESTIMATION: Count products by SKU
  4. PRICE_VERIFICATION: Extract and verify prices

Related:
- Data Model: AnalysisJob, Detection, PriceHistory tables
- ML Modules: ProductDetector, SKUClassifier, StockAnalyzer, PriceOCR
- API Tasks: T036 (analysis router), T038-T039 (workflow)
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


# ============================================
# Enums
# ============================================

class ChallengeType(str, Enum):
    """Supported challenge types."""
    OUT_OF_STOCK = "OUT_OF_STOCK"
    PRODUCT_RECOGNITION = "PRODUCT_RECOGNITION"
    STOCK_ESTIMATION = "STOCK_ESTIMATION"
    PRICE_VERIFICATION = "PRICE_VERIFICATION"


class JobStatus(str, Enum):
    """Analysis job status."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ============================================
# Pydantic Schemas
# ============================================

class AnalysisRequest(BaseModel):
    """Schema for analysis request."""
    challenge_type: ChallengeType = Field(..., description="Challenge to run")
    confidence_threshold: float = Field(0.5, ge=0.0, le=1.0, description="Minimum detection confidence")


class AnalysisJobResponse(BaseModel):
    """Schema for analysis job response."""
    id: int
    image_path: str
    challenge_type: ChallengeType
    status: JobStatus
    result_summary: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class DetectionResponse(BaseModel):
    """Schema for detection response."""
    id: int
    product_id: Optional[int]
    sku: Optional[str]
    bbox: Dict[str, int]  # {"x": 10, "y": 20, "width": 80, "height": 150}
    confidence: float
    label: Optional[str]


class GapResponse(BaseModel):
    """Schema for gap region response."""
    bbox: Dict[str, int]
    gap_width: int
    is_significant: bool


class StockCountResponse(BaseModel):
    """Schema for stock count response."""
    product_id: int
    sku: str
    count: int
    depth_estimate: int
    total_quantity: int
    avg_confidence: float


class PriceVerificationResponse(BaseModel):
    """Schema for price verification response."""
    product_id: int
    sku: str
    detected_price: float
    expected_price: float
    difference: float
    mismatch: bool
    confidence: float


# ============================================
# Router Definition
# ============================================

router = APIRouter(
    prefix="/api/v1/analysis",
    tags=["analysis"],
    responses={404: {"description": "Analysis job not found"}}
)


# ============================================
# Endpoint Contracts
# ============================================

@router.post(
    "/detect",
    response_model=AnalysisJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit shelf image for analysis",
    description="Upload image and run selected challenge type"
)
async def submit_analysis(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(..., description="Shelf image file"),
    challenge_type: ChallengeType = Form(..., description="Challenge to run"),
    confidence_threshold: float = Form(0.5, ge=0.0, le=1.0),
    db: Session = Depends(get_db)
) -> AnalysisJobResponse:
    """
    Submit shelf image for analysis.
    
    Request (multipart/form-data):
        - image: Image file (JPEG, PNG)
        - challenge_type: OUT_OF_STOCK | PRODUCT_RECOGNITION | STOCK_ESTIMATION | PRICE_VERIFICATION
        - confidence_threshold: Minimum confidence (default: 0.5)
    
    Response: 201 Created
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
    
    Process:
        1. Validate image file (format, size < 10MB)
        2. Save image to data/uploads/ with unique name
        3. Create AnalysisJob record (status=PENDING)
        4. Queue background task for processing
        5. Return job details immediately (async processing)
    
    Errors:
        - 400: Invalid image format or size
        - 422: Invalid parameters
    
    Example:
        >>> import httpx
        >>> with open("shelf.jpg", "rb") as f:
        ...     response = httpx.post(
        ...         "http://localhost:8000/api/v1/analysis/detect",
        ...         files={"image": f},
        ...         data={"challenge_type": "OUT_OF_STOCK", "confidence_threshold": 0.7}
        ...     )
        >>> print(response.status_code)
        201
        >>> print(response.json()["id"])
        1
    """
    pass


@router.get(
    "/jobs/{job_id}",
    response_model=AnalysisJobResponse,
    summary="Get analysis job status",
    description="Retrieve analysis job details and results"
)
async def get_analysis_job(
    job_id: int,
    db: Session = Depends(get_db)
) -> AnalysisJobResponse:
    """
    Get analysis job by ID.
    
    Path Parameters:
        - job_id: Analysis job identifier
    
    Response: 200 OK
        {
            "id": 1,
            "image_path": "data/uploads/shelf_20240115_103045.jpg",
            "challenge_type": "OUT_OF_STOCK",
            "status": "COMPLETED",
            "result_summary": {
                "total_products": 45,
                "gaps_detected": 3,
                "gap_regions": [...]
            },
            "error_message": null,
            "created_at": "2024-01-15T10:30:45",
            "completed_at": "2024-01-15T10:31:12"
        }
    
    Errors:
        - 404: Job not found
    
    Implementation:
        1. Query AnalysisJob by id
        2. If not found, raise HTTPException(404)
        3. Return job with current status
    
    Example:
        >>> response = httpx.get("http://localhost:8000/api/v1/analysis/jobs/1")
        >>> job = response.json()
        >>> print(f"Status: {job['status']}")
        Status: COMPLETED
    """
    pass


@router.get(
    "/jobs/{job_id}/detections",
    response_model=List[DetectionResponse],
    summary="Get job detections",
    description="Retrieve all product detections for an analysis job"
)
async def get_job_detections(
    job_id: int,
    db: Session = Depends(get_db)
) -> List[DetectionResponse]:
    """
    Get detections for analysis job.
    
    Response: 200 OK
        [
            {
                "id": 1,
                "product_id": 1,
                "sku": "COKE-500ML",
                "bbox": {"x": 120, "y": 50, "width": 80, "height": 150},
                "confidence": 0.92,
                "label": "COKE-500ML"
            },
            ...
        ]
    
    Errors:
        - 404: Job not found
    
    Implementation:
        1. Verify job exists
        2. Query Detection table filtered by analysis_job_id
        3. Join with Product table to get SKU
        4. Return list of detections
    
    Example:
        >>> response = httpx.get("http://localhost:8000/api/v1/analysis/jobs/1/detections")
        >>> detections = response.json()
        >>> print(f"Found {len(detections)} products")
        Found 24 products
    """
    pass


@router.get(
    "/jobs/{job_id}/gaps",
    response_model=List[GapResponse],
    summary="Get gap regions",
    description="Retrieve gap regions (out-of-stock areas) for analysis job"
)
async def get_job_gaps(
    job_id: int,
    db: Session = Depends(get_db)
) -> List[GapResponse]:
    """
    Get gap regions for OUT_OF_STOCK analysis.
    
    Response: 200 OK
        [
            {
                "bbox": {"x": 450, "y": 60, "width": 120, "height": 180},
                "gap_width": 120,
                "is_significant": true
            },
            ...
        ]
    
    Errors:
        - 404: Job not found
        - 400: Job is not OUT_OF_STOCK type
    
    Implementation:
        1. Verify job exists and challenge_type = OUT_OF_STOCK
        2. Parse result_summary["gap_regions"]
        3. Return list of GapResponse objects
    
    Example:
        >>> response = httpx.get("http://localhost:8000/api/v1/analysis/jobs/1/gaps")
        >>> gaps = response.json()
        >>> significant = [g for g in gaps if g["is_significant"]]
        >>> print(f"Found {len(significant)} significant gaps")
    """
    pass


@router.get(
    "/jobs/{job_id}/stock-counts",
    response_model=List[StockCountResponse],
    summary="Get stock counts",
    description="Retrieve stock counts by SKU for STOCK_ESTIMATION job"
)
async def get_job_stock_counts(
    job_id: int,
    db: Session = Depends(get_db)
) -> List[StockCountResponse]:
    """
    Get stock counts for STOCK_ESTIMATION analysis.
    
    Response: 200 OK
        [
            {
                "product_id": 1,
                "sku": "COKE-500ML",
                "count": 12,
                "depth_estimate": 1,
                "total_quantity": 12,
                "avg_confidence": 0.91
            },
            ...
        ]
    
    Errors:
        - 404: Job not found
        - 400: Job is not STOCK_ESTIMATION type
    
    Implementation:
        1. Verify job exists and challenge_type = STOCK_ESTIMATION
        2. Query detections grouped by product_id
        3. Call StockAnalyzer.count_products()
        4. Return list of StockCountResponse
    
    Example:
        >>> response = httpx.get("http://localhost:8000/api/v1/analysis/jobs/3/stock-counts")
        >>> counts = response.json()
        >>> for count in counts[:5]:
        ...     print(f"{count['sku']}: {count['total_quantity']} units")
    """
    pass


@router.get(
    "/jobs/{job_id}/price-verification",
    response_model=List[PriceVerificationResponse],
    summary="Get price verification results",
    description="Retrieve price verification results for PRICE_VERIFICATION job"
)
async def get_job_price_verification(
    job_id: int,
    db: Session = Depends(get_db)
) -> List[PriceVerificationResponse]:
    """
    Get price verification results.
    
    Response: 200 OK
        [
            {
                "product_id": 1,
                "sku": "COKE-500ML",
                "detected_price": 2.49,
                "expected_price": 1.99,
                "difference": 0.50,
                "mismatch": true,
                "confidence": 0.92
            },
            ...
        ]
    
    Errors:
        - 404: Job not found
        - 400: Job is not PRICE_VERIFICATION type
    
    Implementation:
        1. Verify job exists and challenge_type = PRICE_VERIFICATION
        2. Query PriceHistory table filtered by analysis_job_id
        3. Join with Product table to get SKU
        4. Return list of PriceVerificationResponse
    
    Example:
        >>> response = httpx.get("http://localhost:8000/api/v1/analysis/jobs/4/price-verification")
        >>> results = response.json()
        >>> mismatches = [r for r in results if r["mismatch"]]
        >>> print(f"Found {len(mismatches)} price mismatches")
    """
    pass


# ============================================
# Background Processing
# ============================================

async def process_analysis_job(job_id: int, db_session_factory):
    """
    Background task to process analysis job.
    
    This function is queued by submit_analysis() and runs asynchronously.
    
    Process:
        1. Update job status to PROCESSING
        2. Load image from job.image_path
        3. Route to appropriate challenge handler:
           - OUT_OF_STOCK: process_out_of_stock()
           - PRODUCT_RECOGNITION: process_product_recognition()
           - STOCK_ESTIMATION: process_stock_estimation()
           - PRICE_VERIFICATION: process_price_verification()
        4. Save results to database (detections, gaps, counts, prices)
        5. Update job status to COMPLETED (or FAILED if error)
        6. Store result_summary JSON
    
    Error Handling:
        - Catch all exceptions
        - Set job status = FAILED
        - Store error_message
        - Log error for debugging
    
    Example:
        >>> background_tasks.add_task(process_analysis_job, job_id=1, db_session_factory=SessionLocal)
    """
    pass


def process_out_of_stock(job_id: int, image_path: str, threshold: float, db: Session):
    """
    Process OUT_OF_STOCK challenge (Challenge 1).
    
    Steps:
        1. Initialize ProductDetector
        2. Detect products: detector.detect_products(image_path, threshold)
        3. Detect gaps: detector.detect_gaps(detections, image_width, image_height)
        4. Save Detection records to database
        5. Save result_summary: {"total_products": X, "gaps_detected": Y, "gap_regions": [...]}
    """
    pass


def process_product_recognition(job_id: int, image_path: str, threshold: float, db: Session):
    """
    Process PRODUCT_RECOGNITION challenge (Challenge 2).
    
    Steps:
        1. Initialize SKUClassifier
        2. Classify products: classifier.classify_products(image_path)
        3. Link to catalog: classifier.link_to_catalog(results, catalog)
        4. Save Detection records with product_id
        5. Save result_summary: {"total_products": X, "recognized_skus": [...], "accuracy": Y}
    """
    pass


def process_stock_estimation(job_id: int, image_path: str, threshold: float, db: Session):
    """
    Process STOCK_ESTIMATION challenge (Challenge 3).
    
    Steps:
        1. Initialize SKUClassifier + StockAnalyzer
        2. Classify products and save detections
        3. Count products: analyzer.count_products(detections)
        4. Save result_summary: {"total_products": X, "unique_skus": Y, "stock_counts": [...]}
    """
    pass


def process_price_verification(job_id: int, image_path: str, threshold: float, db: Session):
    """
    Process PRICE_VERIFICATION challenge (Challenge 4).
    
    Steps:
        1. Initialize SKUClassifier + PriceOCR
        2. Classify products to get detections
        3. Extract prices: ocr.extract_prices(image_path)
        4. Verify prices: ocr.verify_prices(image_path, catalog, detections)
        5. Save PriceHistory records
        6. Save result_summary: {"prices_extracted": X, "mismatches": Y, "mismatch_details": [...]}
    """
    pass


# ============================================
# Contract Status
# ============================================

"""
Contract Status: ✅ Complete
Related Tasks:
    - T036: Implement analysis router (POST /detect)
    - T037: Create detections router (GET /detections)
    - T038: Implement analysis job submission workflow
    - T039: Implement ML processing task (background)
    - T041: Create integration tests

API Endpoints:
    - POST /api/v1/analysis/detect              - Submit analysis (async)
    - GET  /api/v1/analysis/jobs/{id}            - Get job status
    - GET  /api/v1/analysis/jobs/{id}/detections - Get detections
    - GET  /api/v1/analysis/jobs/{id}/gaps       - Get gap regions
    - GET  /api/v1/analysis/jobs/{id}/stock-counts - Get stock counts
    - GET  /api/v1/analysis/jobs/{id}/price-verification - Get price results

Challenge Types:
    1. OUT_OF_STOCK: Detect empty shelf spaces
    2. PRODUCT_RECOGNITION: Identify SKUs
    3. STOCK_ESTIMATION: Count products
    4. PRICE_VERIFICATION: Extract and verify prices

Processing Flow:
    1. User uploads image → API returns job_id immediately
    2. Background task processes image asynchronously
    3. User polls GET /jobs/{id} to check status
    4. When status=COMPLETED, results available via specific endpoints

Dependencies:
    - FastAPI (routing, file upload)
    - ProductDetector (Challenge 1)
    - SKUClassifier (Challenge 2, 3)
    - StockAnalyzer (Challenge 3)
    - PriceOCR (Challenge 4)
    - Database (AnalysisJob, Detection, PriceHistory)

Next Steps:
    1. Implement this contract in src/shelf_monitor/api/routers/analysis.py
    2. Implement background processing functions (T038-T039)
    3. Write integration tests in tests/integration/test_api_analysis.py (T041)
    4. Test via Swagger UI at http://localhost:8000/docs
"""
