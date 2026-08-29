# Data Model: Retail Shelf Monitoring

**Project**: Retail Shelf Monitoring with Azure AI and Computer Vision  
**Related**: [plan.md](./plan.md) | [SPECIFICATION.md](../../SPECIFICATION.md) | [tasks.md](./tasks.md)

---

## Overview

This document defines the complete data model for the retail shelf monitoring system, including:
- **5 Database Tables** (SQLAlchemy ORM models for persistence)
- **3 Dataclasses** (Python dataclasses for in-memory processing)

All entities follow these design principles:
- **3NF Normalization**: No redundant data, proper foreign key relationships
- **Type Safety**: Full type hints for all fields
- **Validation**: CHECK constraints at database level, Pydantic validation at API level
- **Auditability**: Timestamps for creation and updates where applicable

---

## Database Tables (SQLAlchemy Models)

### 1. Category Table

**Purpose**: Product category hierarchy for organizing SKUs.

**Table Name**: `categories`

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique category identifier |
| `name` | VARCHAR(100) | NOT NULL, UNIQUE | Category name (e.g., "Beverages", "Snacks") |
| `description` | TEXT | NULLABLE | Optional category description |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Record creation timestamp |

**Indexes**:
- Primary key on `id`
- Unique index on `name`

**Relationships**:
- One-to-Many with `products` (one category has many products)

**Example Data**:
```python
Category(
    id=1,
    name="Beverages",
    description="Soft drinks, juices, water",
    created_at=datetime(2024, 1, 15, 10, 30, 0)
)
```

**SQLAlchemy Model Skeleton**:
```python
class Category(Base):
    __tablename__ = "categories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    products = relationship("Product", back_populates="category")
```

---

### 2. Product Table

**Purpose**: Product catalog with SKU, category, pricing, and expected shelf location.

**Table Name**: `products`

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique product identifier |
| `sku` | VARCHAR(50) | NOT NULL, UNIQUE | Stock Keeping Unit (unique product code) |
| `name` | VARCHAR(200) | NOT NULL | Product name |
| `category_id` | INTEGER | FOREIGN KEY → categories.id, NOT NULL | Category reference |
| `expected_price` | DECIMAL(10, 2) | NOT NULL, CHECK(expected_price >= 0) | Expected retail price |
| `barcode` | VARCHAR(50) | NULLABLE, UNIQUE | Product barcode (EAN/UPC) |
| `image_url` | TEXT | NULLABLE | Product reference image URL |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Record creation timestamp |
| `updated_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP, ON UPDATE | Last update timestamp |

**Indexes**:
- Primary key on `id`
- Unique index on `sku`
- Unique index on `barcode` (if not NULL)
- Foreign key index on `category_id`

**Constraints**:
- `expected_price >= 0` (no negative prices)

**Relationships**:
- Many-to-One with `categories` (many products belong to one category)
- One-to-Many with `detections` (one product can be detected many times)
- One-to-Many with `price_history` (one product has many price records)

**Example Data**:
```python
Product(
    id=1,
    sku="COKE-500ML",
    name="Coca-Cola 500ml",
    category_id=1,
    expected_price=1.99,
    barcode="5449000000996",
    image_url="https://example.com/products/coke-500ml.jpg",
    created_at=datetime(2024, 1, 15, 10, 35, 0),
    updated_at=datetime(2024, 1, 15, 10, 35, 0)
)
```

**SQLAlchemy Model Skeleton**:
```python
class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    expected_price = Column(Numeric(10, 2), CheckConstraint("expected_price >= 0"), nullable=False)
    barcode = Column(String(50), nullable=True, unique=True)
    image_url = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    category = relationship("Category", back_populates="products")
    detections = relationship("Detection", back_populates="product")
    price_history = relationship("PriceHistory", back_populates="product")
```

---

### 3. AnalysisJob Table

**Purpose**: Track each shelf image analysis request (out-of-stock, product recognition, stock count, price verification).

**Table Name**: `analysis_jobs`

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique job identifier |
| `image_path` | TEXT | NOT NULL | Path to uploaded shelf image |
| `challenge_type` | VARCHAR(50) | NOT NULL, CHECK(challenge_type IN (...)) | Challenge: OUT_OF_STOCK, PRODUCT_RECOGNITION, STOCK_ESTIMATION, PRICE_VERIFICATION |
| `status` | VARCHAR(20) | NOT NULL, DEFAULT 'PENDING', CHECK(status IN (...)) | Job status: PENDING, PROCESSING, COMPLETED, FAILED |
| `result_summary` | JSON | NULLABLE | JSON summary of analysis results |
| `error_message` | TEXT | NULLABLE | Error details if status = FAILED |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Job submission timestamp |
| `completed_at` | DATETIME | NULLABLE | Job completion timestamp |

**Indexes**:
- Primary key on `id`
- Index on `status` (for filtering pending/failed jobs)
- Index on `challenge_type` (for filtering by challenge)
- Index on `created_at` (for sorting by date)

**Constraints**:
- `challenge_type` must be one of: `OUT_OF_STOCK`, `PRODUCT_RECOGNITION`, `STOCK_ESTIMATION`, `PRICE_VERIFICATION`
- `status` must be one of: `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`

**Relationships**:
- One-to-Many with `detections` (one job produces many detections)
- One-to-Many with `price_history` (one job may find many prices)

**Example Data**:
```python
AnalysisJob(
    id=1,
    image_path="data/uploads/shelf_20240115_103045.jpg",
    challenge_type="OUT_OF_STOCK",
    status="COMPLETED",
    result_summary={
        "total_products": 45,
        "gaps_detected": 3,
        "gap_regions": [
            {"x": 120, "y": 50, "width": 150, "height": 200},
            {"x": 450, "y": 60, "width": 120, "height": 180}
        ]
    },
    error_message=None,
    created_at=datetime(2024, 1, 15, 10, 30, 45),
    completed_at=datetime(2024, 1, 15, 10, 31, 12)
)
```

**SQLAlchemy Model Skeleton**:
```python
class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    image_path = Column(Text, nullable=False)
    challenge_type = Column(
        String(50), 
        CheckConstraint("challenge_type IN ('OUT_OF_STOCK', 'PRODUCT_RECOGNITION', 'STOCK_ESTIMATION', 'PRICE_VERIFICATION')"),
        nullable=False
    )
    status = Column(
        String(20),
        CheckConstraint("status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')"),
        nullable=False,
        default='PENDING'
    )
    result_summary = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Relationships
    detections = relationship("Detection", back_populates="analysis_job")
    price_history = relationship("PriceHistory", back_populates="analysis_job")
```

---

### 4. Detection Table

**Purpose**: Individual product detections from object detection models (bounding box, confidence, SKU).

**Table Name**: `detections`

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique detection identifier |
| `analysis_job_id` | INTEGER | FOREIGN KEY → analysis_jobs.id, NOT NULL | Analysis job reference |
| `product_id` | INTEGER | FOREIGN KEY → products.id, NULLABLE | Product reference (NULL for unrecognized) |
| `bbox_x` | INTEGER | NOT NULL, CHECK(bbox_x >= 0) | Bounding box top-left X coordinate (pixels) |
| `bbox_y` | INTEGER | NOT NULL, CHECK(bbox_y >= 0) | Bounding box top-left Y coordinate (pixels) |
| `bbox_width` | INTEGER | NOT NULL, CHECK(bbox_width > 0) | Bounding box width (pixels) |
| `bbox_height` | INTEGER | NOT NULL, CHECK(bbox_height > 0) | Bounding box height (pixels) |
| `confidence` | FLOAT | NOT NULL, CHECK(confidence >= 0 AND confidence <= 1) | Model confidence score (0.0-1.0) |
| `label` | VARCHAR(100) | NULLABLE | Detection label from model |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Detection timestamp |

**Indexes**:
- Primary key on `id`
- Foreign key index on `analysis_job_id`
- Foreign key index on `product_id`
- Index on `confidence` (for filtering high-confidence detections)

**Constraints**:
- `bbox_x >= 0`, `bbox_y >= 0` (no negative coordinates)
- `bbox_width > 0`, `bbox_height > 0` (positive dimensions)
- `confidence >= 0 AND confidence <= 1` (valid probability range)

**Relationships**:
- Many-to-One with `analysis_jobs` (many detections belong to one job)
- Many-to-One with `products` (many detections may reference one product)

**Example Data**:
```python
Detection(
    id=1,
    analysis_job_id=1,
    product_id=1,
    bbox_x=120,
    bbox_y=50,
    bbox_width=80,
    bbox_height=150,
    confidence=0.92,
    label="COKE-500ML",
    created_at=datetime(2024, 1, 15, 10, 31, 5)
)
```

**SQLAlchemy Model Skeleton**:
```python
class Detection(Base):
    __tablename__ = "detections"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_job_id = Column(Integer, ForeignKey("analysis_jobs.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    bbox_x = Column(Integer, CheckConstraint("bbox_x >= 0"), nullable=False)
    bbox_y = Column(Integer, CheckConstraint("bbox_y >= 0"), nullable=False)
    bbox_width = Column(Integer, CheckConstraint("bbox_width > 0"), nullable=False)
    bbox_height = Column(Integer, CheckConstraint("bbox_height > 0"), nullable=False)
    confidence = Column(Float, CheckConstraint("confidence >= 0 AND confidence <= 1"), nullable=False)
    label = Column(String(100), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    analysis_job = relationship("AnalysisJob", back_populates="detections")
    product = relationship("Product", back_populates="detections")
```

---

### 5. PriceHistory Table

**Purpose**: Track price tag readings over time for price verification (Challenge 4).

**Table Name**: `price_history`

**Columns**:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT | Unique price record identifier |
| `analysis_job_id` | INTEGER | FOREIGN KEY → analysis_jobs.id, NOT NULL | Analysis job reference |
| `product_id` | INTEGER | FOREIGN KEY → products.id, NOT NULL | Product reference |
| `detected_price` | DECIMAL(10, 2) | NOT NULL, CHECK(detected_price >= 0) | Price extracted via OCR |
| `expected_price` | DECIMAL(10, 2) | NOT NULL, CHECK(expected_price >= 0) | Expected price from product catalog |
| `price_difference` | DECIMAL(10, 2) | GENERATED ALWAYS AS (detected_price - expected_price) STORED | Computed difference |
| `ocr_confidence` | FLOAT | NOT NULL, CHECK(ocr_confidence >= 0 AND ocr_confidence <= 1) | OCR confidence score (0.0-1.0) |
| `bbox_x` | INTEGER | NOT NULL, CHECK(bbox_x >= 0) | Price tag bounding box X |
| `bbox_y` | INTEGER | NOT NULL, CHECK(bbox_y >= 0) | Price tag bounding box Y |
| `bbox_width` | INTEGER | NOT NULL, CHECK(bbox_width > 0) | Price tag bounding box width |
| `bbox_height` | INTEGER | NOT NULL, CHECK(bbox_height > 0) | Price tag bounding box height |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | Price detection timestamp |

**Indexes**:
- Primary key on `id`
- Foreign key index on `analysis_job_id`
- Foreign key index on `product_id`
- Index on `created_at` (for time-series queries)
- Index on `price_difference` (for finding mismatches)

**Constraints**:
- `detected_price >= 0`, `expected_price >= 0` (no negative prices)
- `ocr_confidence >= 0 AND ocr_confidence <= 1` (valid probability range)
- `bbox_x >= 0`, `bbox_y >= 0`, `bbox_width > 0`, `bbox_height > 0` (valid bounding box)
- `price_difference` is a **GENERATED COLUMN** (computed as `detected_price - expected_price`)

**Relationships**:
- Many-to-One with `analysis_jobs` (many price records belong to one job)
- Many-to-One with `products` (many price records reference one product)

**Example Data**:
```python
PriceHistory(
    id=1,
    analysis_job_id=5,
    product_id=1,
    detected_price=2.49,
    expected_price=1.99,
    price_difference=0.50,  # Auto-computed
    ocr_confidence=0.88,
    bbox_x=200,
    bbox_y=120,
    bbox_width=60,
    bbox_height=40,
    created_at=datetime(2024, 1, 15, 14, 20, 30)
)
```

**SQLAlchemy Model Skeleton**:
```python
class PriceHistory(Base):
    __tablename__ = "price_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_job_id = Column(Integer, ForeignKey("analysis_jobs.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    detected_price = Column(Numeric(10, 2), CheckConstraint("detected_price >= 0"), nullable=False)
    expected_price = Column(Numeric(10, 2), CheckConstraint("expected_price >= 0"), nullable=False)
    price_difference = Column(
        Numeric(10, 2),
        Computed("detected_price - expected_price"),
        nullable=False
    )
    ocr_confidence = Column(Float, CheckConstraint("ocr_confidence >= 0 AND ocr_confidence <= 1"), nullable=False)
    bbox_x = Column(Integer, CheckConstraint("bbox_x >= 0"), nullable=False)
    bbox_y = Column(Integer, CheckConstraint("bbox_y >= 0"), nullable=False)
    bbox_width = Column(Integer, CheckConstraint("bbox_width > 0"), nullable=False)
    bbox_height = Column(Integer, CheckConstraint("bbox_height > 0"), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    analysis_job = relationship("AnalysisJob", back_populates="price_history")
    product = relationship("Product", back_populates="price_history")
```

---

## Dataclasses (In-Memory Processing)

These dataclasses are used for in-memory processing in the ML pipeline. They are **not** persisted to the database directly but are converted to database records after processing.

### 6. Detection Dataclass

**Purpose**: Represents a single product detection from Azure Custom Vision or YOLO.

**Module**: `src/shelf_monitor/core/detector.py`

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `bbox` | `tuple[int, int, int, int]` | Bounding box (x, y, width, height) in pixels |
| `confidence` | `float` | Model confidence score (0.0-1.0) |
| `label` | `str` | Detection label (SKU or "product") |
| `product_id` | `int \| None` | Product ID if recognized, None otherwise |

**Usage**: Created by `ProductDetector.detect_products()` and passed to gap detection algorithm.

**Example**:
```python
from dataclasses import dataclass

@dataclass
class Detection:
    bbox: tuple[int, int, int, int]  # (x, y, width, height)
    confidence: float
    label: str
    product_id: int | None = None
    
    def __post_init__(self):
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")
        if self.bbox[2] <= 0 or self.bbox[3] <= 0:
            raise ValueError(f"Invalid bbox dimensions: {self.bbox}")

# Example usage
detection = Detection(
    bbox=(120, 50, 80, 150),
    confidence=0.92,
    label="COKE-500ML",
    product_id=1
)
```

---

### 7. GapRegion Dataclass

**Purpose**: Represents an empty shelf space detected by the gap detection algorithm.

**Module**: `src/shelf_monitor/core/detector.py`

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `bbox` | `tuple[int, int, int, int]` | Gap bounding box (x, y, width, height) in pixels |
| `gap_width` | `int` | Gap width in pixels |
| `is_significant` | `bool` | True if gap_width > threshold (100px) |

**Usage**: Created by `ProductDetector.detect_gaps()` to identify out-of-stock areas.

**Example**:
```python
from dataclasses import dataclass

@dataclass
class GapRegion:
    bbox: tuple[int, int, int, int]  # (x, y, width, height)
    gap_width: int
    is_significant: bool
    
    def __post_init__(self):
        if self.gap_width <= 0:
            raise ValueError(f"Gap width must be positive, got {self.gap_width}")
        if self.bbox[2] <= 0 or self.bbox[3] <= 0:
            raise ValueError(f"Invalid bbox dimensions: {self.bbox}")

# Example usage
gap = GapRegion(
    bbox=(450, 60, 120, 180),
    gap_width=120,
    is_significant=True  # width > 100px threshold
)
```

---

### 8. StockCount Dataclass

**Purpose**: Aggregated stock count per SKU for Challenge 3 (Stock Estimation).

**Module**: `src/shelf_monitor/core/stock_analyzer.py`

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | `int` | Product identifier |
| `sku` | `str` | Stock Keeping Unit |
| `count` | `int` | Number of detected products |
| `depth_estimate` | `int` | Estimated depth (Phase 1: always 1) |
| `total_quantity` | `int` | count × depth_estimate |

**Usage**: Created by `StockAnalyzer.count_products()` to aggregate detections by SKU.

**Example**:
```python
from dataclasses import dataclass

@dataclass
class StockCount:
    product_id: int
    sku: str
    count: int
    depth_estimate: int = 1
    total_quantity: int = 0
    
    def __post_init__(self):
        if self.count < 0:
            raise ValueError(f"Count must be non-negative, got {self.count}")
        if self.depth_estimate < 1:
            raise ValueError(f"Depth estimate must be >= 1, got {self.depth_estimate}")
        # Auto-compute total quantity
        self.total_quantity = self.count * self.depth_estimate

# Example usage
stock = StockCount(
    product_id=1,
    sku="COKE-500ML",
    count=12,
    depth_estimate=1,
    total_quantity=12  # Auto-computed: 12 × 1
)
```

---

## Entity Relationships Diagram (ERD)

```
┌─────────────┐
│  Category   │
│─────────────│
│ id (PK)     │
│ name        │◄──────┐
│ description │       │
│ created_at  │       │ 1:N
└─────────────┘       │
                      │
                 ┌────┴────────┐
                 │   Product   │
                 │─────────────│
                 │ id (PK)     │◄──────┐
                 │ sku         │       │
                 │ name        │       │ 1:N
                 │ category_id │       │
                 │ expected_pr │       │
                 │ barcode     │       │
                 │ image_url   │       │
                 │ created_at  │       │
                 │ updated_at  │       │
                 └─────────────┘       │
                      ▲                │
                      │ 1:N            │
                      │                │
    ┌─────────────────┴────┐           │
    │                      │           │
┌───┴────────┐      ┌──────┴─────┐    │
│ Detection  │      │PriceHistory│    │
│────────────│      │────────────│    │
│ id (PK)    │      │ id (PK)    │    │
│ job_id     │◄──┐  │ job_id     │◄─┐ │
│ product_id │   │  │ product_id │  │ │
│ bbox_x/y   │   │  │ detected_pr│  │ │
│ bbox_w/h   │   │  │ expected_pr│  │ │
│ confidence │   │  │ price_diff │  │ │
│ label      │   │  │ ocr_conf   │  │ │
│ created_at │   │  │ bbox_x/y   │  │ │
└────────────┘   │  │ bbox_w/h   │  │ │
                 │  │ created_at │  │ │
                 │  └────────────┘  │ │
                 │                  │ │
                 │ N:1              │ │
                 │                  │ │
              ┌──┴──────────────┐   │ │
              │  AnalysisJob    │   │ │
              │─────────────────│   │ │
              │ id (PK)         │───┘ │ N:1
              │ image_path      │     │
              │ challenge_type  │     │
              │ status          │─────┘
              │ result_summary  │
              │ error_message   │
              │ created_at      │
              │ completed_at    │
              └─────────────────┘
```

**Relationship Summary**:
1. `Category` → `Product` (1:N) - One category has many products
2. `Product` → `Detection` (1:N) - One product can be detected multiple times
3. `Product` → `PriceHistory` (1:N) - One product has many price records
4. `AnalysisJob` → `Detection` (1:N) - One job produces many detections
5. `AnalysisJob` → `PriceHistory` (1:N) - One job may find many prices

---

## Database Queries (Common Patterns)

### Query 1: Get All Detections for an Analysis Job

```python
# SQL
SELECT * FROM detections WHERE analysis_job_id = ?;

# SQLAlchemy
detections = session.query(Detection).filter(Detection.analysis_job_id == job_id).all()
```

---

### Query 2: Count Products by SKU (Stock Estimation)

```python
# SQL
SELECT 
    p.sku,
    p.name,
    COUNT(d.id) as count
FROM detections d
JOIN products p ON d.product_id = p.id
WHERE d.analysis_job_id = ?
GROUP BY p.sku, p.name
ORDER BY count DESC;

# SQLAlchemy
from sqlalchemy import func

stock_counts = (
    session.query(
        Product.sku,
        Product.name,
        func.count(Detection.id).label('count')
    )
    .join(Detection, Detection.product_id == Product.id)
    .filter(Detection.analysis_job_id == job_id)
    .group_by(Product.sku, Product.name)
    .order_by(func.count(Detection.id).desc())
    .all()
)
```

---

### Query 3: Find Price Mismatches (Price Verification)

```python
# SQL
SELECT 
    p.sku,
    p.name,
    ph.expected_price,
    ph.detected_price,
    ph.price_difference,
    ph.created_at
FROM price_history ph
JOIN products p ON ph.product_id = p.id
WHERE ABS(ph.price_difference) > 0.10  -- Mismatch > 10 cents
ORDER BY ABS(ph.price_difference) DESC;

# SQLAlchemy
from sqlalchemy import func

mismatches = (
    session.query(
        Product.sku,
        Product.name,
        PriceHistory.expected_price,
        PriceHistory.detected_price,
        PriceHistory.price_difference,
        PriceHistory.created_at
    )
    .join(Product, PriceHistory.product_id == Product.id)
    .filter(func.abs(PriceHistory.price_difference) > 0.10)
    .order_by(func.abs(PriceHistory.price_difference).desc())
    .all()
)
```

---

### Query 4: Get Analysis Job with All Detections (Eager Loading)

```python
# SQLAlchemy with relationship eager loading
from sqlalchemy.orm import joinedload

job = (
    session.query(AnalysisJob)
    .options(
        joinedload(AnalysisJob.detections).joinedload(Detection.product)
    )
    .filter(AnalysisJob.id == job_id)
    .first()
)

# Access detections without additional queries
for detection in job.detections:
    print(f"Detected: {detection.product.name} (confidence: {detection.confidence})")
```

---

## Data Validation Rules

### Database Level (CHECK Constraints)

1. **Prices**: Must be non-negative (`>= 0`)
2. **Bounding Boxes**: Coordinates non-negative (`>= 0`), dimensions positive (`> 0`)
3. **Confidence Scores**: Valid probability range (`>= 0 AND <= 1`)
4. **Challenge Types**: Enum validation (only 4 allowed values)
5. **Job Status**: Enum validation (only 4 allowed values)

### Application Level (Pydantic Schemas)

```python
from pydantic import BaseModel, Field, validator

class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    category_id: int = Field(..., gt=0)
    expected_price: float = Field(..., ge=0)
    barcode: str | None = Field(None, max_length=50)
    image_url: str | None = None
    
    @validator('expected_price')
    def validate_price(cls, v):
        if v < 0:
            raise ValueError('Price must be non-negative')
        return round(v, 2)  # Round to 2 decimal places

class DetectionCreate(BaseModel):
    analysis_job_id: int = Field(..., gt=0)
    product_id: int | None = Field(None, gt=0)
    bbox_x: int = Field(..., ge=0)
    bbox_y: int = Field(..., ge=0)
    bbox_width: int = Field(..., gt=0)
    bbox_height: int = Field(..., gt=0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    label: str | None = Field(None, max_length=100)
```

---

## Migration Strategy

### Alembic Migration Order

1. **Migration 001**: Create `categories` table
2. **Migration 001**: Create `products` table (depends on `categories`)
3. **Migration 001**: Create `analysis_jobs` table
4. **Migration 001**: Create `detections` table (depends on `analysis_jobs`, `products`)
5. **Migration 001**: Create `price_history` table (depends on `analysis_jobs`, `products`)

**Note**: All 5 tables will be created in a single migration (T014) since they form a cohesive schema.

### Data Seeding Order (T018)

1. Seed `categories` (from SKU-110K taxonomy)
2. Seed `products` (from SKU-110K annotations)
3. `analysis_jobs`, `detections`, `price_history` populated during runtime

---

## Summary

**Database Tables**: 5 (categories, products, analysis_jobs, detections, price_history)  
**Dataclasses**: 3 (Detection, GapRegion, StockCount)  
**Total Entities**: 8

**Key Features**:
- ✅ 3NF Normalized (no redundant data)
- ✅ Full type hints (Python 3.10+ syntax)
- ✅ CHECK constraints (database-level validation)
- ✅ Foreign key relationships (referential integrity)
- ✅ Generated column (`price_difference` computed automatically)
- ✅ Timestamps (auditability with `created_at`, `updated_at`)
- ✅ Indexes (optimized for common queries)

**Status**: ✅ Data model design complete. Ready for implementation in T010-T013.

**Next Steps**:
1. Implement SQLAlchemy models (T010)
2. Create Pydantic schemas (T011)
3. Implement CRUD operations (T012)
4. Generate Alembic migration (T014)
