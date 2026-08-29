"""
Contract: Database CRUD Operations
Module: src/shelf_monitor/database/crud.py
Purpose: Create, Read, Update, Delete operations for all database tables

This contract defines CRUD functions for 5 database tables:
1. Category: Product categories
2. Product: SKU catalog
3. AnalysisJob: Image analysis requests
4. Detection: Product detections
5. PriceHistory: Price verification records

Related:
- Data Model: data-model.md (5 tables + relationships)
- SQLAlchemy Models: src/shelf_monitor/database/models.py (T010)
- Schemas: src/shelf_monitor/database/schemas.py (T011)
- API Tasks: T012 (CRUD implementation), T071, T086
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta


# ============================================
# Category CRUD
# ============================================

def create_category(db: Session, name: str, description: Optional[str] = None) -> Category:
    """
    Create a new product category.
    
    Args:
        db: Database session
        name: Category name (unique)
        description: Optional category description
    
    Returns:
        Created Category object
    
    Raises:
        ValueError: If category with same name exists
    
    Example:
        >>> from shelf_monitor.database.session import SessionLocal
        >>> db = SessionLocal()
        >>> category = create_category(db, name="Beverages", description="All drinks")
        >>> print(category.id)
        1
    """
    pass


def get_category(db: Session, category_id: int) -> Optional[Category]:
    """
    Get category by ID.
    
    Args:
        db: Database session
        category_id: Category identifier
    
    Returns:
        Category object if found, None otherwise
    
    Example:
        >>> category = get_category(db, category_id=1)
        >>> if category:
        ...     print(category.name)
        Beverages
    """
    pass


def get_category_by_name(db: Session, name: str) -> Optional[Category]:
    """
    Get category by name.
    
    Args:
        db: Database session
        name: Category name
    
    Returns:
        Category object if found, None otherwise
    
    Example:
        >>> category = get_category_by_name(db, name="Beverages")
    """
    pass


def get_categories(
    db: Session,
    skip: int = 0,
    limit: int = 100
) -> List[Category]:
    """
    Get all categories with pagination.
    
    Args:
        db: Database session
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
    
    Returns:
        List of Category objects
    
    Example:
        >>> categories = get_categories(db, skip=0, limit=50)
        >>> print(f"Found {len(categories)} categories")
    """
    pass


def update_category(
    db: Session,
    category_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None
) -> Optional[Category]:
    """
    Update category fields.
    
    Args:
        db: Database session
        category_id: Category identifier
        name: New category name (optional)
        description: New description (optional)
    
    Returns:
        Updated Category object if found, None otherwise
    
    Example:
        >>> category = update_category(db, category_id=1, description="All beverage products")
    """
    pass


def delete_category(db: Session, category_id: int) -> bool:
    """
    Delete category.
    
    Args:
        db: Database session
        category_id: Category identifier
    
    Returns:
        True if deleted, False if not found
    
    Raises:
        ValueError: If category has associated products
    
    Example:
        >>> success = delete_category(db, category_id=1)
    """
    pass


# ============================================
# Product CRUD
# ============================================

def create_product(
    db: Session,
    sku: str,
    name: str,
    category_id: int,
    expected_price: float,
    barcode: Optional[str] = None,
    image_url: Optional[str] = None
) -> Product:
    """
    Create a new product.
    
    Args:
        db: Database session
        sku: Stock Keeping Unit (unique)
        name: Product name
        category_id: Foreign key to categories table
        expected_price: Expected retail price
        barcode: Product barcode (optional)
        image_url: Product image URL (optional)
    
    Returns:
        Created Product object
    
    Raises:
        ValueError: If SKU already exists or category_id invalid
    
    Example:
        >>> product = create_product(
        ...     db,
        ...     sku="COKE-500ML",
        ...     name="Coca-Cola 500ml",
        ...     category_id=1,
        ...     expected_price=1.99,
        ...     barcode="049000050103"
        ... )
        >>> print(product.id)
        1
    """
    pass


def get_product(db: Session, product_id: int) -> Optional[Product]:
    """
    Get product by ID.
    
    Args:
        db: Database session
        product_id: Product identifier
    
    Returns:
        Product object if found, None otherwise
    
    Example:
        >>> product = get_product(db, product_id=1)
    """
    pass


def get_product_by_sku(db: Session, sku: str) -> Optional[Product]:
    """
    Get product by SKU.
    
    Args:
        db: Database session
        sku: Stock Keeping Unit
    
    Returns:
        Product object if found, None otherwise
    
    Example:
        >>> product = get_product_by_sku(db, sku="COKE-500ML")
        >>> print(product.name)
        Coca-Cola 500ml
    """
    pass


def get_products(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    category_id: Optional[int] = None,
    search: Optional[str] = None
) -> List[Product]:
    """
    Get products with pagination and filtering.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records
        category_id: Filter by category (optional)
        search: Search in name or SKU (optional)
    
    Returns:
        List of Product objects
    
    Example:
        >>> # Get all beverages
        >>> products = get_products(db, category_id=1, limit=50)
        >>> 
        >>> # Search for "coke"
        >>> products = get_products(db, search="coke")
    """
    pass


def update_product(
    db: Session,
    product_id: int,
    **kwargs
) -> Optional[Product]:
    """
    Update product fields.
    
    Args:
        db: Database session
        product_id: Product identifier
        **kwargs: Fields to update (name, expected_price, etc.)
    
    Returns:
        Updated Product object if found, None otherwise
    
    Example:
        >>> product = update_product(db, product_id=1, expected_price=2.49)
    """
    pass


def delete_product(db: Session, product_id: int) -> bool:
    """
    Delete product.
    
    Args:
        db: Database session
        product_id: Product identifier
    
    Returns:
        True if deleted, False if not found
    
    Example:
        >>> success = delete_product(db, product_id=1)
    """
    pass


# ============================================
# AnalysisJob CRUD
# ============================================

def create_analysis_job(
    db: Session,
    image_path: str,
    challenge_type: str
) -> AnalysisJob:
    """
    Create a new analysis job.
    
    Args:
        db: Database session
        image_path: Path to uploaded image
        challenge_type: OUT_OF_STOCK | PRODUCT_RECOGNITION | STOCK_ESTIMATION | PRICE_VERIFICATION
    
    Returns:
        Created AnalysisJob object with status=PENDING
    
    Example:
        >>> job = create_analysis_job(
        ...     db,
        ...     image_path="data/uploads/shelf_20240115_103045.jpg",
        ...     challenge_type="OUT_OF_STOCK"
        ... )
        >>> print(job.id)
        1
    """
    pass


def get_analysis_job(db: Session, job_id: int) -> Optional[AnalysisJob]:
    """
    Get analysis job by ID.
    
    Args:
        db: Database session
        job_id: Analysis job identifier
    
    Returns:
        AnalysisJob object if found, None otherwise
    
    Example:
        >>> job = get_analysis_job(db, job_id=1)
        >>> print(job.status)
        COMPLETED
    """
    pass


def get_analysis_jobs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    challenge_type: Optional[str] = None,
    status: Optional[str] = None
) -> List[AnalysisJob]:
    """
    Get analysis jobs with pagination and filtering.
    
    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records
        challenge_type: Filter by challenge type (optional)
        status: Filter by status (optional)
    
    Returns:
        List of AnalysisJob objects
    
    Example:
        >>> # Get all completed jobs
        >>> jobs = get_analysis_jobs(db, status="COMPLETED")
        >>> 
        >>> # Get pending OUT_OF_STOCK jobs
        >>> jobs = get_analysis_jobs(db, challenge_type="OUT_OF_STOCK", status="PENDING")
    """
    pass


def update_analysis_job(
    db: Session,
    job_id: int,
    status: Optional[str] = None,
    result_summary: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    completed_at: Optional[datetime] = None
) -> Optional[AnalysisJob]:
    """
    Update analysis job fields.
    
    Args:
        db: Database session
        job_id: Analysis job identifier
        status: New status (optional)
        result_summary: Analysis results JSON (optional)
        error_message: Error message if failed (optional)
        completed_at: Completion timestamp (optional)
    
    Returns:
        Updated AnalysisJob object if found, None otherwise
    
    Example:
        >>> job = update_analysis_job(
        ...     db,
        ...     job_id=1,
        ...     status="COMPLETED",
        ...     result_summary={"total_products": 45, "gaps_detected": 3},
        ...     completed_at=datetime.now()
        ... )
    """
    pass


# ============================================
# Detection CRUD
# ============================================

def create_detection(
    db: Session,
    analysis_job_id: int,
    bbox_x: int,
    bbox_y: int,
    bbox_width: int,
    bbox_height: int,
    confidence: float,
    label: Optional[str] = None,
    product_id: Optional[int] = None
) -> Detection:
    """
    Create a new product detection.
    
    Args:
        db: Database session
        analysis_job_id: Foreign key to analysis_jobs table
        bbox_x: Bounding box X coordinate
        bbox_y: Bounding box Y coordinate
        bbox_width: Bounding box width
        bbox_height: Bounding box height
        confidence: Detection confidence (0.0-1.0)
        label: Detection label (optional)
        product_id: Foreign key to products table (optional, for recognized products)
    
    Returns:
        Created Detection object
    
    Example:
        >>> detection = create_detection(
        ...     db,
        ...     analysis_job_id=1,
        ...     bbox_x=120,
        ...     bbox_y=50,
        ...     bbox_width=80,
        ...     bbox_height=150,
        ...     confidence=0.92,
        ...     label="COKE-500ML",
        ...     product_id=1
        ... )
    """
    pass


def create_detections_batch(
    db: Session,
    detections: List[Dict[str, Any]]
) -> List[Detection]:
    """
    Create multiple detections in one transaction (bulk insert).
    
    Args:
        db: Database session
        detections: List of detection dictionaries
    
    Returns:
        List of created Detection objects
    
    Example:
        >>> detections = [
        ...     {"analysis_job_id": 1, "bbox_x": 120, "bbox_y": 50, "bbox_width": 80,
        ...      "bbox_height": 150, "confidence": 0.92, "product_id": 1},
        ...     {"analysis_job_id": 1, "bbox_x": 220, "bbox_y": 55, "bbox_width": 75,
        ...      "bbox_height": 145, "confidence": 0.88, "product_id": 2}
        ... ]
        >>> created = create_detections_batch(db, detections)
        >>> print(f"Created {len(created)} detections")
    """
    pass


def get_detection(db: Session, detection_id: int) -> Optional[Detection]:
    """
    Get detection by ID.
    
    Args:
        db: Database session
        detection_id: Detection identifier
    
    Returns:
        Detection object if found, None otherwise
    
    Example:
        >>> detection = get_detection(db, detection_id=1)
    """
    pass


def get_detections_by_job(
    db: Session,
    analysis_job_id: int,
    product_id: Optional[int] = None,
    min_confidence: Optional[float] = None
) -> List[Detection]:
    """
    Get all detections for an analysis job.
    
    Args:
        db: Database session
        analysis_job_id: Analysis job identifier
        product_id: Filter by product (optional)
        min_confidence: Minimum confidence threshold (optional)
    
    Returns:
        List of Detection objects
    
    Example:
        >>> # Get all detections
        >>> detections = get_detections_by_job(db, analysis_job_id=1)
        >>> 
        >>> # Get high-confidence detections of product 1
        >>> detections = get_detections_by_job(db, analysis_job_id=1, product_id=1, min_confidence=0.8)
    """
    pass


def get_detections_by_product(
    db: Session,
    product_id: int,
    skip: int = 0,
    limit: int = 100
) -> List[Detection]:
    """
    Get detection history for a product.
    
    Args:
        db: Database session
        product_id: Product identifier
        skip: Number of records to skip
        limit: Maximum number of records
    
    Returns:
        List of Detection objects
    
    Example:
        >>> # Get recent detections of Coca-Cola
        >>> detections = get_detections_by_product(db, product_id=1, limit=50)
    """
    pass


# ============================================
# PriceHistory CRUD
# ============================================

def create_price_history(
    db: Session,
    analysis_job_id: int,
    product_id: int,
    detected_price: float,
    expected_price: float,
    ocr_confidence: float,
    bbox: Dict[str, int]
) -> PriceHistory:
    """
    Create a new price history record.
    
    Args:
        db: Database session
        analysis_job_id: Foreign key to analysis_jobs table
        product_id: Foreign key to products table
        detected_price: Price extracted from OCR
        expected_price: Expected price from catalog
        ocr_confidence: OCR extraction confidence (0.0-1.0)
        bbox: Price tag bounding box {"x": 10, "y": 20, "width": 50, "height": 30}
    
    Returns:
        Created PriceHistory object (price_difference computed automatically)
    
    Example:
        >>> price = create_price_history(
        ...     db,
        ...     analysis_job_id=1,
        ...     product_id=1,
        ...     detected_price=2.49,
        ...     expected_price=1.99,
        ...     ocr_confidence=0.92,
        ...     bbox={"x": 130, "y": 65, "width": 45, "height": 25}
        ... )
        >>> print(price.price_difference)
        0.50
    """
    pass


def create_price_history_batch(
    db: Session,
    prices: List[Dict[str, Any]]
) -> List[PriceHistory]:
    """
    Create multiple price history records (bulk insert).
    
    Args:
        db: Database session
        prices: List of price dictionaries
    
    Returns:
        List of created PriceHistory objects
    
    Example:
        >>> prices = [
        ...     {"analysis_job_id": 1, "product_id": 1, "detected_price": 2.49,
        ...      "expected_price": 1.99, "ocr_confidence": 0.92, "bbox": {...}},
        ...     {"analysis_job_id": 1, "product_id": 2, "detected_price": 3.99,
        ...      "expected_price": 3.99, "ocr_confidence": 0.88, "bbox": {...}}
        ... ]
        >>> created = create_price_history_batch(db, prices)
    """
    pass


def get_price_history(db: Session, price_history_id: int) -> Optional[PriceHistory]:
    """
    Get price history record by ID.
    
    Args:
        db: Database session
        price_history_id: Price history identifier
    
    Returns:
        PriceHistory object if found, None otherwise
    
    Example:
        >>> price = get_price_history(db, price_history_id=1)
    """
    pass


def get_price_history_by_job(
    db: Session,
    analysis_job_id: int,
    mismatches_only: bool = False
) -> List[PriceHistory]:
    """
    Get price history for an analysis job.
    
    Args:
        db: Database session
        analysis_job_id: Analysis job identifier
        mismatches_only: If True, return only price mismatches (optional)
    
    Returns:
        List of PriceHistory objects
    
    Example:
        >>> # Get all price records
        >>> prices = get_price_history_by_job(db, analysis_job_id=1)
        >>> 
        >>> # Get only mismatches
        >>> mismatches = get_price_history_by_job(db, analysis_job_id=1, mismatches_only=True)
    """
    pass


def get_price_history_by_product(
    db: Session,
    product_id: int,
    days: int = 30,
    skip: int = 0,
    limit: int = 100
) -> List[PriceHistory]:
    """
    Get price history for a product.
    
    Args:
        db: Database session
        product_id: Product identifier
        days: Number of days to look back (default: 30)
        skip: Number of records to skip
        limit: Maximum number of records
    
    Returns:
        List of PriceHistory objects ordered by created_at DESC
    
    Example:
        >>> # Get price history for last 30 days
        >>> prices = get_price_history_by_product(db, product_id=1, days=30)
        >>> 
        >>> # Get last 7 days
        >>> recent = get_price_history_by_product(db, product_id=1, days=7, limit=20)
    """
    pass


# ============================================
# Aggregation Queries
# ============================================

def count_products_by_sku(
    db: Session,
    analysis_job_id: int,
    min_confidence: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Aggregate detections by SKU for stock counting.
    
    Args:
        db: Database session
        analysis_job_id: Analysis job identifier
        min_confidence: Minimum confidence threshold
    
    Returns:
        List of dictionaries:
        [
            {"product_id": 1, "sku": "COKE-500ML", "count": 12, "avg_confidence": 0.91},
            {"product_id": 2, "sku": "PEPSI-500ML", "count": 8, "avg_confidence": 0.87},
            ...
        ]
    
    SQL:
        SELECT 
            product_id, 
            sku, 
            COUNT(*) as count, 
            AVG(confidence) as avg_confidence
        FROM detections
        JOIN products ON detections.product_id = products.id
        WHERE analysis_job_id = ? AND confidence >= ?
        GROUP BY product_id, sku
        ORDER BY count DESC
    
    Example:
        >>> counts = count_products_by_sku(db, analysis_job_id=1, min_confidence=0.7)
        >>> for item in counts:
        ...     print(f"{item['sku']}: {item['count']} units (confidence: {item['avg_confidence']:.2f})")
    """
    pass


def get_price_mismatches(
    db: Session,
    analysis_job_id: Optional[int] = None,
    threshold: float = 0.10,
    skip: int = 0,
    limit: int = 100
) -> List[PriceHistory]:
    """
    Get price mismatches (detected != expected).
    
    Args:
        db: Database session
        analysis_job_id: Filter by job (optional, None = all jobs)
        threshold: Mismatch threshold in dollars (default: $0.10)
        skip: Number of records to skip
        limit: Maximum number of records
    
    Returns:
        List of PriceHistory objects where ABS(price_difference) > threshold
    
    SQL:
        SELECT *
        FROM price_history
        WHERE ABS(price_difference) > ?
        [AND analysis_job_id = ?]
        ORDER BY ABS(price_difference) DESC
        LIMIT ? OFFSET ?
    
    Example:
        >>> # Get all mismatches > $0.10
        >>> mismatches = get_price_mismatches(db, threshold=0.10)
        >>> 
        >>> # Get mismatches for specific job
        >>> mismatches = get_price_mismatches(db, analysis_job_id=1, threshold=0.05)
    """
    pass


def get_stock_trends(
    db: Session,
    product_id: int,
    days: int = 30
) -> List[Dict[str, Any]]:
    """
    Get stock count trends over time for a product.
    
    Args:
        db: Database session
        product_id: Product identifier
        days: Number of days to analyze
    
    Returns:
        List of dictionaries:
        [
            {"date": "2024-01-15", "count": 12, "job_count": 3},
            {"date": "2024-01-16", "count": 10, "job_count": 2},
            ...
        ]
    
    SQL:
        SELECT 
            DATE(analysis_jobs.created_at) as date,
            COUNT(detections.id) as count,
            COUNT(DISTINCT analysis_jobs.id) as job_count
        FROM detections
        JOIN analysis_jobs ON detections.analysis_job_id = analysis_jobs.id
        WHERE detections.product_id = ?
          AND analysis_jobs.created_at >= DATE('now', '-? days')
        GROUP BY DATE(analysis_jobs.created_at)
        ORDER BY date DESC
    
    Example:
        >>> trends = get_stock_trends(db, product_id=1, days=7)
        >>> for day in trends:
        ...     print(f"{day['date']}: {day['count']} detections ({day['job_count']} jobs)")
    """
    pass


# ============================================
# Contract Status
# ============================================

"""
Contract Status: ✅ Complete
Related Tasks:
    - T012: Implement CRUD operations
    - T071: Implement stock aggregation queries
    - T086: Implement price history CRUD
    - T088: Implement price mismatch queries

Functions:
    Category CRUD: 6 functions (create, get, get_by_name, list, update, delete)
    Product CRUD: 7 functions (create, get, get_by_sku, list, update, delete, search)
    AnalysisJob CRUD: 5 functions (create, get, list, update, filter)
    Detection CRUD: 6 functions (create, create_batch, get, get_by_job, get_by_product, filter)
    PriceHistory CRUD: 6 functions (create, create_batch, get, get_by_job, get_by_product, filter)
    Aggregation Queries: 3 functions (count_by_sku, price_mismatches, stock_trends)

Total: 33 functions covering all database operations

Database Tables:
    1. categories (2 fields)
    2. products (8 fields)
    3. analysis_jobs (7 fields)
    4. detections (8 fields)
    5. price_history (8 fields + 1 generated column)

Query Patterns:
    - Basic CRUD (create, read, update, delete)
    - Pagination (skip, limit)
    - Filtering (category_id, status, challenge_type, confidence)
    - Search (name, SKU)
    - Aggregation (COUNT, AVG, GROUP BY)
    - Time-series (date ranges, trends)
    - Joins (product_id, analysis_job_id foreign keys)

Performance:
    - Indexes on foreign keys (product_id, analysis_job_id, category_id)
    - Bulk insert support (create_batch functions)
    - Query optimization (JOIN only when needed)
    - Pagination for large result sets

Next Steps:
    1. Implement this contract in src/shelf_monitor/database/crud.py (T012)
    2. Use SQLAlchemy models from models.py (T010)
    3. Write unit tests in tests/unit/test_crud.py
    4. Test aggregation queries for correctness
"""
