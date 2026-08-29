"""
Database CRUD Operations: Create, Read, Update, Delete for all tables.

This module implements CRUD functions for 5 database tables:
1. Category: Product categories
2. Product: SKU catalog with pricing and barcode
3. AnalysisJob: Image analysis requests and results
4. Detection: Product detections with bounding boxes
5. PriceHistory: Price verification records over time

Features:
- Full CRUD operations (create, read, update, delete)
- Pagination support (skip, limit)
- Filtering (category, status, challenge type, confidence)
- Search capabilities (SKU, product name)
- Bulk insert operations (batch create)
- Aggregation queries (stock counts, price mismatches, trends)

Related:
- Contract: .specify/plans/contracts/crud.py
- Models: src/shelf_monitor/database/models.py
- Schemas: src/shelf_monitor/database/schemas.py
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.shelf_monitor.database.models import (
    AnalysisJob,
    Category,
    Detection,
    PriceHistory,
    Product,
)


# ============================================================================
# Category CRUD
# ============================================================================


def create_category(
    db: Session, name: str, description: Optional[str] = None
) -> Category:
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
        >>> db = SessionLocal()
        >>> category = create_category(db, name="Beverages", description="All drinks")
        >>> print(category.id)
        1
    """
    # Check if category with same name exists
    existing = get_category_by_name(db, name)
    if existing:
        raise ValueError(f"Category with name '{name}' already exists")

    category = Category(name=name, description=description)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


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
    return db.query(Category).filter(Category.id == category_id).first()


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
    return db.query(Category).filter(Category.name == name).first()


def get_categories(db: Session, skip: int = 0, limit: int = 100) -> List[Category]:
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
    return db.query(Category).offset(skip).limit(limit).all()


def update_category(
    db: Session,
    category_id: int,
    name: Optional[str] = None,
    description: Optional[str] = None,
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
    category = get_category(db, category_id)
    if not category:
        return None

    if name is not None:
        # Check if new name conflicts with existing category
        existing = get_category_by_name(db, name)
        if existing and existing.id != category_id:
            raise ValueError(f"Category with name '{name}' already exists")
        category.name = name

    if description is not None:
        category.description = description

    db.commit()
    db.refresh(category)
    return category


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
    category = get_category(db, category_id)
    if not category:
        return False

    # Check if category has products
    if category.products:
        raise ValueError(
            f"Cannot delete category '{category.name}': {len(category.products)} products exist"
        )

    db.delete(category)
    db.commit()
    return True


# ============================================================================
# Product CRUD
# ============================================================================


def create_product(
    db: Session,
    sku: str,
    name: str,
    category_id: int,
    expected_price: float,
    barcode: Optional[str] = None,
    image_url: Optional[str] = None,
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
    # Check if SKU already exists
    existing = get_product_by_sku(db, sku)
    if existing:
        raise ValueError(f"Product with SKU '{sku}' already exists")

    # Verify category exists
    category = get_category(db, category_id)
    if not category:
        raise ValueError(f"Category with id {category_id} does not exist")

    product = Product(
        sku=sku,
        name=name,
        category_id=category_id,
        expected_price=expected_price,
        barcode=barcode,
        image_url=image_url,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


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
    return db.query(Product).filter(Product.id == product_id).first()


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
    return db.query(Product).filter(Product.sku == sku).first()


def get_product_by_barcode(db: Session, barcode: str) -> Optional[Product]:
    """
    Get product by barcode.

    Args:
        db: Database session
        barcode: Product barcode

    Returns:
        Product object if found, None otherwise

    Example:
        >>> product = get_product_by_barcode(db, barcode="049000050103")
    """
    return db.query(Product).filter(Product.barcode == barcode).first()


def get_products(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    category_id: Optional[int] = None,
    search: Optional[str] = None,
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
    query = db.query(Product)

    # Filter by category
    if category_id is not None:
        query = query.filter(Product.category_id == category_id)

    # Search in name or SKU (case-insensitive)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Product.name.ilike(search_pattern),
                Product.sku.ilike(search_pattern),
            )
        )

    return query.offset(skip).limit(limit).all()


def update_product(db: Session, product_id: int, **kwargs) -> Optional[Product]:
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
    product = get_product(db, product_id)
    if not product:
        return None

    # Update allowed fields
    allowed_fields = {
        "name",
        "category_id",
        "expected_price",
        "barcode",
        "image_url",
    }

    for key, value in kwargs.items():
        if key in allowed_fields and value is not None:
            # Validate category_id if provided
            if key == "category_id":
                category = get_category(db, value)
                if not category:
                    raise ValueError(f"Category with id {value} does not exist")
            setattr(product, key, value)

    product.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(product)
    return product


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
    product = get_product(db, product_id)
    if not product:
        return False

    db.delete(product)
    db.commit()
    return True


# ============================================================================
# AnalysisJob CRUD
# ============================================================================


def create_analysis_job(db: Session, image_path: str, challenge_type: str) -> AnalysisJob:
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
    job = AnalysisJob(image_path=image_path, challenge_type=challenge_type)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


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
    return db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()


def get_analysis_jobs(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    challenge_type: Optional[str] = None,
    status: Optional[str] = None,
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
    query = db.query(AnalysisJob)

    if challenge_type:
        query = query.filter(AnalysisJob.challenge_type == challenge_type)

    if status:
        query = query.filter(AnalysisJob.status == status)

    return query.order_by(AnalysisJob.created_at.desc()).offset(skip).limit(limit).all()


def get_analysis_jobs_by_status(db: Session, status: str) -> List[AnalysisJob]:
    """
    Get all analysis jobs with specific status.

    Args:
        db: Database session
        status: Job status (PENDING, PROCESSING, COMPLETED, FAILED)

    Returns:
        List of AnalysisJob objects

    Example:
        >>> pending_jobs = get_analysis_jobs_by_status(db, "PENDING")
    """
    return db.query(AnalysisJob).filter(AnalysisJob.status == status).all()


def update_analysis_job(
    db: Session,
    job_id: int,
    status: Optional[str] = None,
    result_summary: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    completed_at: Optional[datetime] = None,
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
    job = get_analysis_job(db, job_id)
    if not job:
        return None

    if status is not None:
        job.status = status

    if result_summary is not None:
        job.result_summary = result_summary

    if error_message is not None:
        job.error_message = error_message

    if completed_at is not None:
        job.completed_at = completed_at

    db.commit()
    db.refresh(job)
    return job


# ============================================================================
# Detection CRUD
# ============================================================================


def create_detection(
    db: Session,
    analysis_job_id: int,
    bbox_x: int,
    bbox_y: int,
    bbox_width: int,
    bbox_height: int,
    confidence: float,
    label: Optional[str] = None,
    product_id: Optional[int] = None,
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
    detection = Detection(
        analysis_job_id=analysis_job_id,
        product_id=product_id,
        bbox_x=bbox_x,
        bbox_y=bbox_y,
        bbox_width=bbox_width,
        bbox_height=bbox_height,
        confidence=confidence,
        label=label,
    )
    db.add(detection)
    db.commit()
    db.refresh(detection)
    return detection


def create_detections_batch(db: Session, detections: List[Dict[str, Any]]) -> List[Detection]:
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
    detection_objects = [Detection(**det) for det in detections]
    db.add_all(detection_objects)
    db.commit()
    for det in detection_objects:
        db.refresh(det)
    return detection_objects


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
    return db.query(Detection).filter(Detection.id == detection_id).first()


def get_detections_by_job(
    db: Session,
    analysis_job_id: int,
    product_id: Optional[int] = None,
    min_confidence: Optional[float] = None,
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
    query = db.query(Detection).filter(Detection.analysis_job_id == analysis_job_id)

    if product_id is not None:
        query = query.filter(Detection.product_id == product_id)

    if min_confidence is not None:
        query = query.filter(Detection.confidence >= min_confidence)

    return query.all()


def get_detections_by_product(
    db: Session, product_id: int, skip: int = 0, limit: int = 100
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
    return (
        db.query(Detection)
        .filter(Detection.product_id == product_id)
        .order_by(Detection.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def count_detections_by_job(db: Session, analysis_job_id: int) -> int:
    """
    Count total detections for an analysis job.

    Args:
        db: Database session
        analysis_job_id: Analysis job identifier

    Returns:
        Total detection count

    Example:
        >>> count = count_detections_by_job(db, analysis_job_id=1)
        >>> print(f"Found {count} products")
    """
    return db.query(Detection).filter(Detection.analysis_job_id == analysis_job_id).count()


# ============================================================================
# PriceHistory CRUD
# ============================================================================


def create_price_history(
    db: Session,
    analysis_job_id: int,
    product_id: int,
    detected_price: float,
    expected_price: float,
    ocr_confidence: float,
    bbox_x: int,
    bbox_y: int,
    bbox_width: int,
    bbox_height: int,
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
        bbox_x: Price tag bounding box X
        bbox_y: Price tag bounding box Y
        bbox_width: Price tag bounding box width
        bbox_height: Price tag bounding box height

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
        ...     bbox_x=130,
        ...     bbox_y=65,
        ...     bbox_width=45,
        ...     bbox_height=25
        ... )
        >>> print(price.price_difference)
        0.50
    """
    price = PriceHistory(
        analysis_job_id=analysis_job_id,
        product_id=product_id,
        detected_price=detected_price,
        expected_price=expected_price,
        ocr_confidence=ocr_confidence,
        bbox_x=bbox_x,
        bbox_y=bbox_y,
        bbox_width=bbox_width,
        bbox_height=bbox_height,
    )
    db.add(price)
    db.commit()
    db.refresh(price)
    return price


def create_price_history_batch(db: Session, prices: List[Dict[str, Any]]) -> List[PriceHistory]:
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
        ...      "expected_price": 1.99, "ocr_confidence": 0.92,
        ...      "bbox_x": 130, "bbox_y": 65, "bbox_width": 45, "bbox_height": 25},
        ...     {"analysis_job_id": 1, "product_id": 2, "detected_price": 3.99,
        ...      "expected_price": 3.99, "ocr_confidence": 0.88,
        ...      "bbox_x": 230, "bbox_y": 70, "bbox_width": 50, "bbox_height": 30}
        ... ]
        >>> created = create_price_history_batch(db, prices)
    """
    price_objects = [PriceHistory(**price) for price in prices]
    db.add_all(price_objects)
    db.commit()
    for price in price_objects:
        db.refresh(price)
    return price_objects


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
    return db.query(PriceHistory).filter(PriceHistory.id == price_history_id).first()


def get_price_history_by_job(
    db: Session, analysis_job_id: int, mismatches_only: bool = False
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
    query = db.query(PriceHistory).filter(PriceHistory.analysis_job_id == analysis_job_id)

    if mismatches_only:
        query = query.filter(PriceHistory.price_difference != 0)

    return query.all()


def get_price_history_by_product(
    db: Session, product_id: int, days: int = 30, skip: int = 0, limit: int = 100
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
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    return (
        db.query(PriceHistory)
        .filter(
            and_(
                PriceHistory.product_id == product_id,
                PriceHistory.created_at >= cutoff_date,
            )
        )
        .order_by(PriceHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


# ============================================================================
# Aggregation Queries
# ============================================================================


def count_products_by_sku(
    db: Session, analysis_job_id: int, min_confidence: float = 0.5
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

    Example:
        >>> counts = count_products_by_sku(db, analysis_job_id=1, min_confidence=0.7)
        >>> for item in counts:
        ...     print(f"{item['sku']}: {item['count']} units (confidence: {item['avg_confidence']:.2f})")
    """
    results = (
        db.query(
            Detection.product_id,
            Product.sku,
            func.count(Detection.id).label("count"),
            func.avg(Detection.confidence).label("avg_confidence"),
        )
        .join(Product, Detection.product_id == Product.id)
        .filter(
            and_(
                Detection.analysis_job_id == analysis_job_id,
                Detection.confidence >= min_confidence,
                Detection.product_id.isnot(None),
            )
        )
        .group_by(Detection.product_id, Product.sku)
        .order_by(func.count(Detection.id).desc())
        .all()
    )

    return [
        {
            "product_id": row.product_id,
            "sku": row.sku,
            "count": row.count,
            "avg_confidence": float(row.avg_confidence),
        }
        for row in results
    ]


def get_price_mismatches(
    db: Session,
    analysis_job_id: Optional[int] = None,
    threshold: float = 0.10,
    skip: int = 0,
    limit: int = 100,
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

    Example:
        >>> # Get all mismatches > $0.10
        >>> mismatches = get_price_mismatches(db, threshold=0.10)
        >>>
        >>> # Get mismatches for specific job
        >>> mismatches = get_price_mismatches(db, analysis_job_id=1, threshold=0.05)
    """
    query = db.query(PriceHistory).filter(
        or_(
            PriceHistory.price_difference > threshold,
            PriceHistory.price_difference < -threshold,
        )
    )

    if analysis_job_id is not None:
        query = query.filter(PriceHistory.analysis_job_id == analysis_job_id)

    return (
        query.order_by(
            func.abs(PriceHistory.price_difference).desc()
        )
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_stock_trends(db: Session, product_id: int, days: int = 30) -> List[Dict[str, Any]]:
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

    Example:
        >>> trends = get_stock_trends(db, product_id=1, days=7)
        >>> for day in trends:
        ...     print(f"{day['date']}: {day['count']} detections ({day['job_count']} jobs)")
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    results = (
        db.query(
            func.date(AnalysisJob.created_at).label("date"),
            func.count(Detection.id).label("count"),
            func.count(func.distinct(AnalysisJob.id)).label("job_count"),
        )
        .join(Detection, AnalysisJob.id == Detection.analysis_job_id)
        .filter(
            and_(
                Detection.product_id == product_id,
                AnalysisJob.created_at >= cutoff_date,
            )
        )
        .group_by(func.date(AnalysisJob.created_at))
        .order_by(func.date(AnalysisJob.created_at).desc())
        .all()
    )

    return [
        {
            "date": str(row.date),
            "count": row.count,
            "job_count": row.job_count,
        }
        for row in results
    ]
