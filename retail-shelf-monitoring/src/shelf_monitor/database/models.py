"""
Database Models: SQLAlchemy ORM models for retail shelf monitoring.

This module defines 5 database tables:
1. Category: Product categories (beverages, snacks, etc.)
2. Product: Product catalog with SKU, pricing, barcode
3. AnalysisJob: Image analysis tracking (out-of-stock, recognition, etc.)
4. Detection: Individual product detections with bounding boxes
5. PriceHistory: Price verification records over time

All models follow:
- 3NF normalization (no redundant data)
- Full type hints for IDE support
- CHECK constraints for validation
- Proper indexes for query performance
- Relationships using SQLAlchemy ORM

Related:
- Data Model: .specify/plans/data-model.md
- Schemas: src/shelf_monitor/database/schemas.py (Pydantic validation)
- CRUD: src/shelf_monitor/database/crud.py (database operations)
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Numeric,
    Float,
    ForeignKey,
    CheckConstraint,
    JSON,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship, Mapped
from sqlalchemy.schema import Computed


# Base class for all models
Base = declarative_base()


class Category(Base):
    """
    Product category for organizing SKUs.
    
    One category can have many products (one-to-many relationship).
    
    Attributes:
        id: Unique category identifier
        name: Category name (unique, e.g., "Beverages", "Snacks")
        description: Optional category description
        created_at: Record creation timestamp
        products: Related Product objects
    
    Example:
        >>> category = Category(
        ...     name="Beverages",
        ...     description="Soft drinks, juices, water"
        ... )
        >>> db.add(category)
        >>> db.commit()
    """
    
    __tablename__ = "categories"
    
    # Columns
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = Column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = Column(Text, nullable=True)
    created_at: Mapped[datetime] = Column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    # Relationships
    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="category", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Category(id={self.id}, name={self.name!r})>"


class Product(Base):
    """
    Product catalog with SKU, category, pricing, and barcode.
    
    Each product belongs to one category (many-to-one relationship).
    Each product can have many detections and price records.
    
    Attributes:
        id: Unique product identifier
        sku: Stock Keeping Unit (unique product code)
        name: Product name
        category_id: Foreign key to categories table
        expected_price: Expected retail price (must be >= 0)
        barcode: Optional product barcode (EAN/UPC)
        image_url: Optional product reference image URL
        created_at: Record creation timestamp
        updated_at: Last update timestamp (auto-updated)
        category: Related Category object
        detections: Related Detection objects
        price_history: Related PriceHistory objects
    
    Example:
        >>> product = Product(
        ...     sku="COKE-500ML",
        ...     name="Coca-Cola 500ml",
        ...     category_id=1,
        ...     expected_price=1.99,
        ...     barcode="5449000000996"
        ... )
        >>> db.add(product)
        >>> db.commit()
    """
    
    __tablename__ = "products"
    
    # Columns
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = Column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = Column(String(200), nullable=False)
    category_id: Mapped[int] = Column(
        Integer, ForeignKey("categories.id"), nullable=False, index=True
    )
    expected_price: Mapped[float] = Column(
        Numeric(10, 2), CheckConstraint("expected_price >= 0"), nullable=False
    )
    barcode: Mapped[Optional[str]] = Column(String(50), nullable=True, unique=True)
    image_url: Mapped[Optional[str]] = Column(Text, nullable=True)
    created_at: Mapped[datetime] = Column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    detections: Mapped[List["Detection"]] = relationship(
        "Detection", back_populates="product"
    )
    price_history: Mapped[List["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="product"
    )
    
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku={self.sku!r}, name={self.name!r})>"


class AnalysisJob(Base):
    """
    Track shelf image analysis requests.
    
    Each job processes one image for a specific challenge type:
    - OUT_OF_STOCK: Detect empty shelf spaces
    - PRODUCT_RECOGNITION: Identify SKUs
    - STOCK_ESTIMATION: Count products per SKU
    - PRICE_VERIFICATION: Extract and verify prices
    
    Job lifecycle: PENDING → PROCESSING → COMPLETED/FAILED
    
    Attributes:
        id: Unique job identifier
        image_path: Path to uploaded shelf image
        challenge_type: Challenge being executed (see enum above)
        status: Job status (PENDING, PROCESSING, COMPLETED, FAILED)
        result_summary: JSON summary of analysis results
        error_message: Error details if status = FAILED
        created_at: Job submission timestamp
        completed_at: Job completion timestamp
        detections: Related Detection objects
        price_history: Related PriceHistory objects
    
    Example:
        >>> job = AnalysisJob(
        ...     image_path="data/uploads/shelf_20240115_103045.jpg",
        ...     challenge_type="OUT_OF_STOCK",
        ...     status="PENDING"
        ... )
        >>> db.add(job)
        >>> db.commit()
    """
    
    __tablename__ = "analysis_jobs"
    
    # Columns
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    image_path: Mapped[str] = Column(Text, nullable=False)
    challenge_type: Mapped[str] = Column(
        String(50),
        CheckConstraint(
            "challenge_type IN ('OUT_OF_STOCK', 'PRODUCT_RECOGNITION', "
            "'STOCK_ESTIMATION', 'PRICE_VERIFICATION')"
        ),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = Column(
        String(20),
        CheckConstraint("status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')"),
        nullable=False,
        default="PENDING",
        index=True,
    )
    result_summary: Mapped[Optional[dict]] = Column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = Column(Text, nullable=True)
    created_at: Mapped[datetime] = Column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    completed_at: Mapped[Optional[datetime]] = Column(DateTime, nullable=True)
    
    # Relationships
    detections: Mapped[List["Detection"]] = relationship(
        "Detection", back_populates="analysis_job", cascade="all, delete-orphan"
    )
    price_history: Mapped[List["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="analysis_job", cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return (
            f"<AnalysisJob(id={self.id}, challenge_type={self.challenge_type!r}, "
            f"status={self.status!r})>"
        )


class Detection(Base):
    """
    Individual product detection from object detection models.
    
    Stores bounding box, confidence score, and optional product linkage.
    Used for Challenges 1-3 (out-of-stock, recognition, stock counting).
    
    Attributes:
        id: Unique detection identifier
        analysis_job_id: Foreign key to analysis_jobs table
        product_id: Foreign key to products table (NULL for unrecognized)
        bbox_x: Bounding box top-left X coordinate (pixels, >= 0)
        bbox_y: Bounding box top-left Y coordinate (pixels, >= 0)
        bbox_width: Bounding box width (pixels, > 0)
        bbox_height: Bounding box height (pixels, > 0)
        confidence: Model confidence score (0.0-1.0)
        label: Detection label from model (optional)
        created_at: Detection timestamp
        analysis_job: Related AnalysisJob object
        product: Related Product object (if recognized)
    
    Example:
        >>> detection = Detection(
        ...     analysis_job_id=1,
        ...     product_id=5,
        ...     bbox_x=120,
        ...     bbox_y=50,
        ...     bbox_width=80,
        ...     bbox_height=150,
        ...     confidence=0.92,
        ...     label="COKE-500ML"
        ... )
        >>> db.add(detection)
        >>> db.commit()
    """
    
    __tablename__ = "detections"
    
    # Columns
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    analysis_job_id: Mapped[int] = Column(
        Integer, ForeignKey("analysis_jobs.id"), nullable=False, index=True
    )
    product_id: Mapped[Optional[int]] = Column(
        Integer, ForeignKey("products.id"), nullable=True, index=True
    )
    bbox_x: Mapped[int] = Column(
        Integer, CheckConstraint("bbox_x >= 0"), nullable=False
    )
    bbox_y: Mapped[int] = Column(
        Integer, CheckConstraint("bbox_y >= 0"), nullable=False
    )
    bbox_width: Mapped[int] = Column(
        Integer, CheckConstraint("bbox_width > 0"), nullable=False
    )
    bbox_height: Mapped[int] = Column(
        Integer, CheckConstraint("bbox_height > 0"), nullable=False
    )
    confidence: Mapped[float] = Column(
        Float,
        CheckConstraint("confidence >= 0 AND confidence <= 1"),
        nullable=False,
        index=True,
    )
    label: Mapped[Optional[str]] = Column(String(100), nullable=True)
    created_at: Mapped[datetime] = Column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    
    # Relationships
    analysis_job: Mapped["AnalysisJob"] = relationship(
        "AnalysisJob", back_populates="detections"
    )
    product: Mapped[Optional["Product"]] = relationship(
        "Product", back_populates="detections"
    )
    
    def __repr__(self) -> str:
        return (
            f"<Detection(id={self.id}, job_id={self.analysis_job_id}, "
            f"product_id={self.product_id}, confidence={self.confidence:.2f})>"
        )


class PriceHistory(Base):
    """
    Track price tag readings over time for price verification.
    
    Used for Challenge 4 (price verification). Compares detected prices
    from OCR against expected prices from product catalog.
    
    The price_difference column is a GENERATED COLUMN (computed automatically
    as detected_price - expected_price).
    
    Attributes:
        id: Unique price record identifier
        analysis_job_id: Foreign key to analysis_jobs table
        product_id: Foreign key to products table
        detected_price: Price extracted via OCR (>= 0)
        expected_price: Expected price from product catalog (>= 0)
        price_difference: Computed as detected_price - expected_price (GENERATED)
        ocr_confidence: OCR confidence score (0.0-1.0)
        bbox_x: Price tag bounding box X (>= 0)
        bbox_y: Price tag bounding box Y (>= 0)
        bbox_width: Price tag bounding box width (> 0)
        bbox_height: Price tag bounding box height (> 0)
        created_at: Price detection timestamp
        analysis_job: Related AnalysisJob object
        product: Related Product object
    
    Example:
        >>> price = PriceHistory(
        ...     analysis_job_id=5,
        ...     product_id=1,
        ...     detected_price=2.49,
        ...     expected_price=1.99,
        ...     ocr_confidence=0.88,
        ...     bbox_x=200, bbox_y=120,
        ...     bbox_width=60, bbox_height=40
        ... )
        >>> db.add(price)
        >>> db.commit()
        >>> print(price.price_difference)  # Auto-computed: 0.50
    """
    
    __tablename__ = "price_history"
    
    # Columns
    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    analysis_job_id: Mapped[int] = Column(
        Integer, ForeignKey("analysis_jobs.id"), nullable=False, index=True
    )
    product_id: Mapped[int] = Column(
        Integer, ForeignKey("products.id"), nullable=False, index=True
    )
    detected_price: Mapped[float] = Column(
        Numeric(10, 2), CheckConstraint("detected_price >= 0"), nullable=False
    )
    expected_price: Mapped[float] = Column(
        Numeric(10, 2), CheckConstraint("expected_price >= 0"), nullable=False
    )
    price_difference: Mapped[float] = Column(
        Numeric(10, 2),
        Computed("detected_price - expected_price"),
        nullable=False,
        index=True,
    )
    ocr_confidence: Mapped[float] = Column(
        Float, CheckConstraint("ocr_confidence >= 0 AND ocr_confidence <= 1"), nullable=False
    )
    bbox_x: Mapped[int] = Column(
        Integer, CheckConstraint("bbox_x >= 0"), nullable=False
    )
    bbox_y: Mapped[int] = Column(
        Integer, CheckConstraint("bbox_y >= 0"), nullable=False
    )
    bbox_width: Mapped[int] = Column(
        Integer, CheckConstraint("bbox_width > 0"), nullable=False
    )
    bbox_height: Mapped[int] = Column(
        Integer, CheckConstraint("bbox_height > 0"), nullable=False
    )
    created_at: Mapped[datetime] = Column(
        DateTime, nullable=False, default=datetime.utcnow, index=True
    )
    
    # Relationships
    analysis_job: Mapped["AnalysisJob"] = relationship(
        "AnalysisJob", back_populates="price_history"
    )
    product: Mapped["Product"] = relationship("Product", back_populates="price_history")
    
    def __repr__(self) -> str:
        return (
            f"<PriceHistory(id={self.id}, job_id={self.analysis_job_id}, "
            f"product_id={self.product_id}, detected=${self.detected_price}, "
            f"expected=${self.expected_price}, diff=${self.price_difference})>"
        )


# Additional indexes for common query patterns
Index("idx_detections_job_product", Detection.analysis_job_id, Detection.product_id)
Index("idx_price_history_job_product", PriceHistory.analysis_job_id, PriceHistory.product_id)
Index("idx_price_history_created", PriceHistory.created_at.desc())
