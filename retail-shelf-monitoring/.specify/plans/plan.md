# Implementation Plan: Retail Shelf Monitoring

**Branch**: `main` (learning project - no feature branches) | **Date**: December 10, 2025 | **Spec**: [SPECIFICATION.md](../../SPECIFICATION.md)

**Input**: Feature specification from `SPECIFICATION.md` + Constitution from `.specify/memory/constitution.md`

---

## Summary

Implement a learning-focused retail shelf monitoring system addressing 2 critical challenges using Computer Vision. The project teaches junior Python developers object detection with YOLO, and production Python practices through hands-on implementation with SKU-110K public dataset (11,762 images, single "object" class). Deliverables include working Python modules, Jupyter notebooks for demonstration, and comprehensive educational documentation.

**Primary Requirement**: Educational value first, production structure second  
**Technical Approach**: Sequential implementation (Challenge 1→Challenge 2), single-class YOLO training, notebook-based demonstration

---

## Technical Context

**Language/Version**: Python 3.10+  
**Primary Dependencies**: 
- **ML/CV**: PyTorch 2.0+, Ultralytics (YOLOv8), OpenCV, Pillow
- **Data**: NumPy, Pandas, matplotlib, seaborn
- **Backend**: FastAPI 0.104+, SQLAlchemy 2.0+, Alembic (migrations), Pydantic
- **Database**: SQLite 3+ (development and testing)
- **Dev**: pytest, black, flake8, mypy, python-dotenv, httpx (API testing)

**Storage**: 
- Local filesystem for datasets (data/)
- SQLite database for analysis results
- Trained YOLO models stored locally (models/)

**Testing**: 
- pytest (unit tests for core ML logic, API endpoints, database operations)
- Coverage target: >70% for core/ and api/ modules
- Integration tests: FastAPI TestClient with SQLite in-memory database

**Target Platform**: 
- Local development (macOS/Linux/Windows)
- Jupyter notebooks for ML demonstration
- FastAPI backend with RESTful API (localhost:8000)
- SQLite database (data/retail_shelf_monitoring.db)

**Project Type**: Full-stack learning project
- Python ML package (src/shelf_monitor/core/)
- FastAPI backend (src/shelf_monitor/api/)
- Database layer (src/shelf_monitor/database/)
- Jupyter notebooks for demonstration

**Performance Goals**:
- Challenge 1: Precision >90%, Recall >85%, <500ms latency (M1/M2 or NVIDIA GPU)
- Challenge 2: Count accuracy >95%, <100ms processing time

**Constraints**:
- **Cost**: $0 (all free tools and datasets)
- **Timeline**: 6 weeks sequential implementation
- **Audience**: Junior Python developers (6-12 months experience)
- **Complexity**: Simple implementations (<50 LOC per function), no microservices/K8s/real-time streaming

**Scale/Scope**: 
- 2 ML challenges, ~11,000 training images (SKU-110K), 2 notebooks
- RESTful API with 8-10 endpoints (analysis submission, results retrieval)
- 3 database tables (analysis_jobs, detections, optional products)
- 4 guide documents (challenge_1, challenge_2, yolo_training, api_development)
- Single developer learning project, not production deployment

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ Learning-First Approach (FOUNDATIONAL)
- [x] **Target Audience**: Junior Python developers (6-12 months experience) ✅
- [x] **Complexity Serves Education**: 4 focused challenges, public datasets, no production complexity ✅
- [x] **Simple Scenarios**: No microservices, K8s, real-time streaming, edge deployment ✅
- [x] **Clear Code**: <50 LOC functions, readable over clever, educational error messages ✅

### ✅ Production-Standard Structure, Simple Implementation
- [x] **Package Layout**: src/, tests/, proper __init__.py ✅
- [x] **One Class Per File**: detector.py, classifier.py, stock_analyzer.py, ocr.py ✅
- [x] **Separation of Concerns**: core/ (logic), models/ (ML), services/ (Azure), utils/ (helpers) ✅
- [x] **Type Hints + Docstrings**: Mandatory (Google/NumPy style) ✅
- [x] **Single Responsibility**: Each module has clear purpose ✅

### ✅ Educational Documentation (MANDATORY)
- [x] **Markdown Guides Required**: What/Why/How/Key Concepts/Usage/Next Steps for all 4 ML challenges + backend development ✅
- [x] **Location**: docs/guides/ ✅
- [x] **Coverage**: 
  - ML: challenge_1_oos_detection.md, challenge_2_product_recognition.md, challenge_3_stock_estimation.md, challenge_4_price_verification.md
  - Infrastructure: azure_setup.md, yolo_training.md, database_design.md, api_development.md ✅

### ✅ Code Quality for Learning
- [x] **Clear Naming**: Avoid abbreviations ✅
- [x] **Small Functions**: <50 lines preferred ✅
- [x] **Why Comments**: Explain rationale, not mechanics ✅
- [x] **Flat Structure**: Avoid deep nesting ✅
- [x] **Teaching Errors**: "What + Why + How to fix" in error messages ✅
- [x] **Visibility**: Log intermediate steps for learning ✅

### ⚠️ Potential Violations Requiring Justification

| Item | Status | Justification |
|------|--------|---------------|
| **4 ML Challenges + Backend** | ⚠️ Complexity | Justified: Each ML challenge teaches distinct CV concept. Backend (FastAPI + SQL) teaches full-stack skills. Sequential implementation prevents overwhelm. |
| **Azure + Local YOLO** | ⚠️ Dual approach | Justified: Azure Custom Vision for fast prototyping/cloud learning, YOLO for deep CV understanding. Educational comparison value. |
| **Phase 1-4 Model** | ⚠️ 4 phases | Justified: Enforces incremental learning (get working → clean → better → production). Constitution Principle V. |
| **Database + API Layer** | ⚠️ Added stack | Justified: User explicitly requested SQL/data modeling/FastAPI learning. Adds backend skills to CV project. Database stores product catalog for realistic scenario. |

**Gate Result**: ✅ **PASS** - All violations justified for educational value. Proceed to Phase 0.

---

## Project Structure

### Documentation (this project)

```text
.specify/
├── plans/
│   ├── plan.md              # This file
│   ├── research.md          # Phase 0: Technology decisions, best practices
│   ├── data-model.md        # Phase 1: Entity models, data structures
│   └── quickstart.md        # Phase 1: Getting started guide
├── checklists/
│   └── requirements-quality.md  # Quality gate checklist (completed)
├── memory/
│   └── constitution.md      # Project principles
└── templates/               # Spec/plan templates

docs/
├── guides/                  # Educational documentation (MANDATORY)
│   ├── challenge_1_oos_detection.md
│   ├── challenge_2_product_recognition.md
│   ├── challenge_3_stock_estimation.md
│   ├── challenge_4_price_verification.md
│   ├── azure_setup.md
│   ├── yolo_training.md
│   ├── database_design.md      # SQL schema, migrations, indexes
│   └── api_development.md      # FastAPI endpoints, authentication
├── ARCHITECTURE.md          # Optional (can recreate with backend architecture)
└── LEARNING_PATH.md         # 10-week curriculum (exists)

SPECIFICATION.md             # Complete requirements (exists)
README.md                    # Project overview (exists)
```

### Source Code (repository root)

```text
retail-shelf-monitoring/
├── src/shelf_monitor/       # Main application package
│   ├── __init__.py
│   ├── core/                # ML business logic (4 challenges)
│   │   ├── __init__.py
│   │   ├── detector.py      # Challenge 1: ProductDetector class
│   │   ├── classifier.py    # Challenge 2: SKUClassifier class
│   │   ├── stock_analyzer.py # Challenge 3: StockAnalyzer class
│   │   └── ocr.py           # Challenge 4: PriceOCR class
│   ├── models/              # ML model wrappers
│   │   ├── __init__.py
│   │   └── yolo.py          # YOLOv8Detector wrapper
│   ├── database/            # Database layer (SQLAlchemy)
│   │   ├── __init__.py
│   │   ├── models.py        # ORM models (Product, Category, AnalysisJob, Detection, PriceHistory)
│   │   ├── schemas.py       # Pydantic schemas for validation
│   │   ├── crud.py          # CRUD operations
│   │   └── session.py       # Database connection management
│   ├── api/                 # FastAPI backend
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI app initialization
│   │   ├── dependencies.py  # Dependency injection (DB session, auth)
│   │   └── routers/         # API route modules
│   │       ├── __init__.py
│   │       ├── products.py  # Product CRUD endpoints
│   │       ├── analysis.py  # Submit/retrieve analysis jobs
│   │       ├── detections.py # Query detection results
│   │       └── health.py    # Health check endpoints
│   ├── services/            # Azure service integrations
│   │   ├── __init__.py
│   │   ├── azure_custom_vision.py
│   │   └── azure_document_intelligence.py
│   ├── config/              # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py      # Load .env, Azure + DB credentials
│   └── utils/               # Shared utilities
│       ├── __init__.py
│       ├── image.py         # Image preprocessing utilities
│       └── logging.py       # Logging configuration
│
├── notebooks/               # Jupyter notebooks (demonstration + code)
│   ├── 01_out_of_stock_detection.ipynb
│   ├── 02_product_recognition.ipynb
│   ├── 03_stock_level_estimation.ipynb
│   └── 04_price_tag_verification.ipynb
│
├── data/                    # Datasets (gitignored except structure)
│   ├── raw/                 # Original downloads
│   │   ├── SKU110K/
│   │   ├── GroceryStore/
│   │   └── RPC/
│   ├── processed/           # Preprocessed for training
│   │   ├── train/
│   │   ├── val/
│   │   └── test/
│   └── annotations/         # COCO/YOLO format labels
│
├── models/                  # Trained model artifacts (gitignored)
│   ├── custom_vision_oos.pkl
│   ├── yolov8_products.pt
│   └── README.md            # Model versioning info
│
├── tests/                   # Test suite
│   ├── __init__.py
│   ├── unit/                # Unit tests (ML core logic)
│   │   ├── test_detector.py
│   │   ├── test_classifier.py
│   │   ├── test_stock_analyzer.py
│   │   └── test_ocr.py
│   ├── integration/         # Integration tests (API + DB)
│   │   ├── test_api_products.py
│   │   ├── test_api_analysis.py
│   │   └── test_database_crud.py
│   └── conftest.py          # pytest fixtures (TestClient, test DB)
│
├── scripts/                 # Utility scripts
│   ├── download_dataset.py  # Download SKU-110K, etc.
│   ├── prepare_data.py      # Preprocess and split data
│   ├── setup_azure.py       # Provision Azure resources
│   ├── init_database.py     # Create database and run migrations
│   └── seed_products.py     # Populate product catalog from dataset
│
├── alembic/                 # Database migrations
│   ├── versions/            # Migration scripts
│   ├── env.py
│   └── alembic.ini
│
├── .env.example             # Template for credentials
├── .gitignore
├── requirements.txt         # Pinned dependencies
├── requirements-dev.txt     # Dev dependencies (pytest, black, etc.)
├── setup.py                 # Package installation
└── pytest.ini               # pytest configuration
```

**Structure Decision**: Full-stack Python application selected because:
- Learning project teaching ML + Backend + Database skills
- Backend API layer (FastAPI) for RESTful interactions
- Database layer (SQLite + SQLAlchemy) for persistent storage
- ML core remains modular (4 challenges)
- Notebooks interact with API for demonstration
- Follows Python best practices (PEP 517/518 compatible)
- Clean separation: core/ (ML), database/ (ORM), api/ (REST)

---

## Complexity Tracking

> Filled because Constitution Check identified 3 justified violations

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **4 Challenges** | Retail shelf monitoring naturally decomposes into 4 distinct problems (out-of-stock, recognition, counting, price verification). Each teaches different AI/CV concept. | Single "detect products" challenge insufficient to teach full stack (object detection, classification, counting, OCR). 2-3 challenges leave gaps in learning. |
| **Azure + Local YOLO** | Azure Custom Vision provides rapid prototyping and cloud AI learning. YOLOv8 provides deep CV understanding and performance comparison. Educational value in contrasting approaches. | Azure-only: Misses local ML training and PyTorch ecosystem. YOLO-only: Misses Azure AI services (primary learning goal). Dual approach justified for comprehensive learning. |
| **Phase 1-4 Progression** | Enforces incremental complexity as per Constitution Principle V. Prevents junior developers from attempting everything at once (error handling, optimization, tests simultaneously). | Single-pass implementation: Violates learning-first principle. Junior developers overwhelmed by trying to write production-quality code immediately. Phases teach iteration. |

---

## Phase 0: Research & Technical Decisions

**Goal**: Resolve all "NEEDS CLARIFICATION" from Technical Context and establish best practices for each technology choice.

### Research Tasks

#### R1: Dataset Analysis & Preparation Strategy
**Question**: How to efficiently download, preprocess, and manage 11K+ images from SKU-110K while staying within Azure Custom Vision F0 5K image limit?

**Research Activities**:
- Analyze SKU-110K dataset structure (COCO format, annotation quality)
- Determine subset selection strategy (4K images for Custom Vision, full 11K for YOLO)
- Investigate COCO → YOLO annotation conversion tools
- Define train/val/test split ratios (70/15/15)
- Document data augmentation needs (if any)

**Decision to Document**:
- Subset selection criteria (random sampling vs stratified)
- Preprocessing pipeline (resize, normalize, augment)
- Storage strategy (local vs Azure Blob)

**Output**: `research.md` section "Dataset Management Strategy"

---

#### R2: Azure Custom Vision Best Practices
**Question**: How to maximize learning from Custom Vision F0 tier (2 projects, 10 training iterations) for Challenges 1 & 2?

**Research Activities**:
- Review Azure Custom Vision quickstart and SDK documentation
- Identify F0 tier limitations and workarounds
- Determine optimal image upload batch size
- Research iteration planning (when to train vs when to add more data)
- Investigate quota monitoring approaches

**Decision to Document**:
- Project allocation (1 for OOS detection, 1 for product recognition)
- Training iteration strategy (start with 500 images, evaluate, add more)
- Fallback plan if quota exhausted (switch to YOLO)

**Output**: `research.md` section "Azure Custom Vision Strategy"

---

#### R3: YOLOv8 Training Configuration
**Question**: What YOLOv8 model size, hyperparameters, and hardware setup for Challenge 2 on junior developer machines?

**Research Activities**:
- Compare YOLOv8n (nano), YOLOv8s (small), YOLOv8m (medium) for accuracy vs speed
- Determine hardware requirements (CPU vs GPU, VRAM needs)
- Research transfer learning from COCO pretrained weights
- Identify optimal training hyperparameters (epochs, batch size, learning rate)
- Investigate training time estimates

**Decision to Document**:
- Model size: YOLOv8s (balance of speed and accuracy for learning)
- Hardware: M1/M2 Mac or NVIDIA GPU (6GB+ VRAM), CPU fallback acceptable
- Hyperparameters: 50 epochs, batch size 16, pretrained weights from COCO
- Expected training time: 2-4 hours on GPU

**Output**: `research.md` section "YOLO Training Configuration"

---

#### R4: Azure Document Intelligence Integration
**Question**: How to use pre-trained OCR for price tag extraction without custom training?

**Research Activities**:
- Review Azure Document Intelligence (Form Recognizer) pre-built models
- Identify "Read API" vs "Layout API" for price tag text extraction
- Determine API call patterns and rate limiting (15 req/min F0)
- Research price parsing regex patterns ($X.XX, €X,XX, £X.XX)
- Investigate confidence thresholding

**Decision to Document**:
- API choice: Read API (sufficient for price text extraction)
- Retry strategy: Exponential backoff for rate limiting
- Parsing approach: Regex with fallback to fuzzy matching
- Confidence threshold: >0.8 for accepted prices

**Output**: `research.md` section "Document Intelligence OCR Strategy"

---

#### R5: Error Handling Patterns
**Question**: What retry, logging, and user feedback patterns for Azure API failures and quota limits?

**Research Activities**:
- Research Azure SDK error types (HTTP 429, 401, 500, timeout)
- Identify retry best practices (exponential backoff, max attempts)
- Determine logging strategy (console vs file, log levels)
- Design educational error messages ("what + why + fix")
- Investigate quota monitoring approaches

**Decision to Document**:
- Retry: 3 attempts, exponential backoff (1s, 2s, 4s)
- Logging: Console logging with structured format, DEBUG level for development
- Error messages: Include original error + context + actionable fix
- Quota monitoring: Log API call counts, warn at 80% threshold

**Output**: `research.md` section "Error Handling & Resilience"

---

#### R6: Testing Strategy for Learning Project
**Question**: What test coverage and mocking approach balances learning value with pragmatism?

**Research Activities**:
- Review pytest best practices for ML projects and FastAPI
- Determine mocking strategy for Azure SDK (avoid real API calls in tests)
- Research FastAPI TestClient for API endpoint testing
- Identify database testing approach (SQLite in-memory for tests)
- Identify core logic requiring tests (gap detection, counting, parsing, CRUD operations)
- Research coverage tools (coverage.py, pytest-cov)
- Balance test effort with educational ROI

**Decision to Document**:
- Coverage target: >70% for core/ and api/ modules (not strict requirement)
- Mocking: Use pytest-mock for Azure API calls, real logic tested
- API Testing: FastAPI TestClient with dependency override for test DB
- Database Testing: SQLite in-memory for unit tests, separate SQLite file for integration tests
- Test scope: Unit tests for pure Python logic + CRUD, integration tests for API workflows
- CI: Not required (learning project), run locally before commits

**Output**: `research.md` section "Testing Approach"

---

---

#### R7: Database Schema Design & SQL Best Practices
**Question**: How to design normalized PostgreSQL schema for product catalog, analysis results, and price tracking while teaching SQL fundamentals?

**Research Activities**:
- Design entity-relationship diagram (Products, Categories, AnalysisJobs, Detections, PriceHistory)
- Determine normalization level (3NF target for learning clarity)
- Research indexing strategy (primary keys, foreign keys, common query indexes)
- Investigate SQLAlchemy ORM patterns vs raw SQL
- Define migration strategy (Alembic for schema versioning)
- Research connection pooling and session management

**Decision to Document**:
- Schema: 5 tables (products, categories, analysis_jobs, detections, price_history)
- Relationships: Many-to-one (products → categories), one-to-many (analysis_jobs → detections)
- Indexes: Primary keys (auto), foreign keys, composite index on (analysis_job_id, sku) for detections
- ORM: SQLAlchemy 2.0 style (async optional for Phase 2+), expose raw SQL in educational comments
- Migrations: Alembic for version control, teach "why migrations matter"

**Output**: `research.md` section "Database Design Strategy"

---

#### R8: FastAPI Architecture & RESTful API Design
**Question**: How to structure FastAPI application with clean separation, dependency injection, and RESTful best practices for learning?

**Research Activities**:
- Review FastAPI project structure patterns (routers, dependencies, middleware)
- Design RESTful endpoint hierarchy (/api/v1/products, /api/v1/analysis)
- Research dependency injection for database sessions (yield pattern)
- Investigate request/response validation with Pydantic schemas
- Define authentication strategy (optional: API key for Phase 2+, skip for Phase 1)
- Research error handling and HTTP status codes

**Decision to Document**:
- Structure: Routers by domain (products, analysis, detections, health)
- Endpoints: 12-15 total (5 product CRUD, 3 analysis, 3 detection query, 1 health)
- Dependency Injection: Database session via `Depends(get_db)`, yielding pattern
- Validation: Pydantic schemas for request bodies, SQLAlchemy models for DB
- Authentication: Skip for Phase 1 (localhost only), add API key in Phase 2 if needed
- Error Handling: Custom exception handlers, educational error messages with "what + why + fix"

**Output**: `research.md` section "FastAPI Architecture Strategy"

---

### Research Consolidation

**Output File**: `.specify/plans/research.md`

**Format**:
```markdown
# Research Findings - Retail Shelf Monitoring

## Decision: Dataset Management Strategy
**Chosen**: Use SKU-110K subset (4K images) for Custom Vision, full dataset (11K) for YOLO training.
**Rationale**: Stays within Azure F0 5K limit while maximizing learning. YOLO benefits from larger dataset.
**Alternatives Considered**: 
- Single 5K dataset for both: Rejected, limits YOLO learning potential
- Cloud-only storage: Rejected, adds cost and complexity for learning project

## Decision: Database Design Strategy
**Chosen**: PostgreSQL with 5 normalized tables (3NF), SQLAlchemy ORM, Alembic migrations.
**Rationale**: PostgreSQL teaches production SQL, normalization reinforces data modeling concepts, ORM provides Pythonic interface while exposing raw SQL for learning.
**Alternatives Considered**:
- SQLite: Rejected, want to learn production database (PostgreSQL)
- NoSQL (MongoDB): Rejected, SQL explicitly requested for learning
- Denormalized schema: Rejected, defeats data modeling learning goal

## Decision: FastAPI Architecture Strategy
[Similar format for R8...]

## Decision: Azure Custom Vision Strategy
[Similar format for each remaining research task...]
```

---

## Phase 1: Design & Contracts

**Goal**: Define data models, API contracts, and implementation roadmap before coding.

**Prerequisites**: `research.md` complete, all NEEDS CLARIFICATION resolved

### D1: Data Model Definition

**Output File**: `.specify/plans/data-model.md`

**Entities to Model**:

#### Entity: Product (Database Table)
**Purpose**: Stores product catalog with SKU metadata
**Fields**:
- `id: int` - Primary key (auto-increment)
- `sku: str` - Unique SKU identifier (e.g., "coca_cola_500ml")
- `name: str` - Display name (e.g., "Coca Cola 500ml")
- `category_id: int` - Foreign key to categories table
- `expected_price: Decimal(10,2)` - Reference price for verification
- `barcode: str` - Optional barcode (EAN-13)
- `image_url: str` - Optional product image URL
- `created_at: DateTime` - Timestamp
- `updated_at: DateTime` - Timestamp

**Validation Rules**:
- `sku` must be unique, non-empty, max 100 chars
- `expected_price` must be positive
- `category_id` must reference valid category

**Indexes**: 
- Primary key on `id`
- Unique index on `sku`
- Foreign key index on `category_id`

---

#### Entity: Category (Database Table)
**Purpose**: Product categories for organization
**Fields**:
- `id: int` - Primary key
- `name: str` - Category name (e.g., "Beverages", "Snacks")
- `description: str` - Optional description

**Relationships**: One-to-many with Product

---

#### Entity: AnalysisJob (Database Table)
**Purpose**: Tracks analysis runs for shelf images
**Fields**:
- `id: int` - Primary key
- `image_path: str` - Path to analyzed image
- `challenge_type: Enum` - One of: OOS_DETECTION, PRODUCT_RECOGNITION, STOCK_ESTIMATION, PRICE_VERIFICATION
- `status: Enum` - One of: PENDING, PROCESSING, COMPLETED, FAILED
- `created_at: DateTime`
- `completed_at: DateTime`
- `error_message: str` - If status=FAILED

**Relationships**: One-to-many with Detection

---

#### Entity: Detection (Database Table + Dataclass)
**Purpose**: Individual product detections from analysis
**Database Fields**:
- `id: int` - Primary key
- `analysis_job_id: int` - Foreign key to analysis_jobs
- `sku: str` - Detected SKU (foreign key to products)
- `bbox_x: int` - Bounding box x
- `bbox_y: int` - Bounding box y
- `bbox_width: int` - Bounding box width
- `bbox_height: int` - Bounding box height
- `confidence: float` - Detection confidence (0.0-1.0)
- `label: str` - Detected class label

**Dataclass Fields** (for in-memory passing):
- `bbox: Tuple[int, int, int, int]` - Bounding box (x, y, width, height)
- `confidence: float` - Detection confidence score (0.0-1.0)
- `label: str` - Detected class/SKU label
- `image_id: str` - Source image identifier

**Validation Rules**:
- `confidence` must be in range [0.0, 1.0]
- `bbox` values must be positive integers
- `sku` should reference valid product (soft constraint for learning)

**Indexes**:
- Primary key on `id`
- Foreign key on `analysis_job_id`
- Composite index on `(analysis_job_id, sku)` for aggregation queries

---

#### Entity: PriceHistory (Database Table)
**Purpose**: Track price changes over time from OCR analysis
**Fields**:
- `id: int` - Primary key
- `sku: str` - Foreign key to products
- `detected_price: Decimal(10,2)` - Price extracted from image
- `expected_price: Decimal(10,2)` - Reference price at time of detection
- `price_difference: Decimal(10,2)` - Calculated difference
- `confidence: float` - OCR confidence
- `image_path: str` - Source image
- `detected_at: DateTime` - Timestamp

**Relationships**: Many-to-one with Product

**Indexes**:
- Primary key on `id`
- Foreign key on `sku`
- Index on `detected_at` for time-series queries

---

#### Entity: GapRegion (Dataclass - In-Memory Only)
**Purpose**: Represents an empty shelf space (out-of-stock) during analysis
**Fields**:
- `bbox: Tuple[int, int, int, int]` - Gap bounding box
- `width_px: int` - Gap width in pixels
- `is_critical: bool` - Exceeds threshold (True if width_px > MIN_GAP_THRESHOLD)

**Validation Rules**:
- `width_px` must be positive
- `MIN_GAP_THRESHOLD` configurable (default 100px)

**Note**: Not persisted to database (transient analysis result)

---

#### Entity: ProductCount (Dataclass - In-Memory Only)
**Purpose**: Aggregated stock count per SKU during analysis
**Fields**:
- `sku: str` - Product SKU identifier
- `count: int` - Number of detections
- `estimated_depth: int` - Shelf depth estimate (rows)
- `total_estimate: int` - `count * estimated_depth`

**Validation Rules**:
- `count` must be non-negative
- `estimated_depth` defaults to 1, can be 2-3 based on heuristics

**Note**: Aggregated from Detection table queries, not stored directly

---

#### Entity: PriceTag (Dataclass - In-Memory Only)
**Purpose**: Extracted price information from image during OCR analysis
**Fields**:
- `bbox: Tuple[int, int, int, int]` - Price tag location
- `text: str` - Raw OCR text
- `price: Optional[float]` - Parsed price value
- `currency: str` - Currency symbol ($, €, £)
- `confidence: float` - OCR confidence (0.0-1.0)

**Validation Rules**:
- `price` must be positive if not None
- `currency` must be in ['$', '€', '£', 'USD', 'EUR', 'GBP']

**Note**: Transient during analysis, results saved to PriceHistory table

---

**Relationships**:
- **Product ↔ Category**: Many-to-one (many products belong to one category)
- **Product ↔ PriceHistory**: One-to-many (one product has many price observations)
- **AnalysisJob ↔ Detection**: One-to-many (one analysis produces many detections)
- **Product ↔ Detection**: Referenced via `sku` (soft foreign key for flexibility)
- **GapRegion, ProductCount, PriceTag**: In-memory dataclasses (not persisted)

---

### D2: API Contracts

**Output Files**: 
- `.specify/plans/contracts/` directory (Python module interfaces)
- `.specify/plans/api-spec.yaml` (OpenAPI 3.0 specification for REST API)

#### Contract: `core/detector.py`

```python
# src/shelf_monitor/core/detector.py

from typing import List, Tuple
from pathlib import Path
from dataclasses import dataclass

@dataclass(frozen=True)
class Detection:
    """Represents a detected product in shelf image."""
    bbox: Tuple[int, int, int, int]  # (x, y, width, height)
    confidence: float  # 0.0-1.0
    label: str
    image_id: str

@dataclass(frozen=True)
class GapRegion:
    """Represents an empty shelf space (out-of-stock)."""
    bbox: Tuple[int, int, int, int]
    width_px: int
    is_critical: bool

class ProductDetector:
    """
    Detects products in shelf images using Azure Custom Vision.
    Implements Challenge 1 (Out-of-Stock Detection).
    """
    
    def __init__(self, endpoint: str, key: str, project_id: str, iteration_name: str) -> None:
        """
        Initialize detector with Azure Custom Vision credentials.
        
        Args:
            endpoint: Azure Custom Vision prediction endpoint URL
            key: Azure Custom Vision prediction key
            project_id: Custom Vision project ID (GUID)
            iteration_name: Published iteration name (e.g., "Iteration1")
        """
        pass
    
    def detect_products(self, image_path: Path) -> List[Detection]:
        """
        Detect all products in shelf image.
        
        Args:
            image_path: Path to shelf image (JPEG/PNG, min 640x480)
            
        Returns:
            List of Detection objects with bounding boxes and confidence scores
            
        Raises:
            ValueError: If image_path does not exist or invalid format
            AzureError: If API call fails (retries 3x before raising)
            QuotaExceededError: If monthly prediction limit exceeded (10K/month F0)
        """
        pass
    
    def detect_gaps(self, detections: List[Detection], image_width: int, 
                   min_gap_px: int = 100) -> List[GapRegion]:
        """
        Identify empty shelf spaces from product detections.
        
        Args:
            detections: List of Detection objects from detect_products()
            image_width: Image width in pixels (for boundary detection)
            min_gap_px: Minimum gap width to flag as critical (default 100px)
            
        Returns:
            List of GapRegion objects representing out-of-stock areas
            
        Algorithm:
            1. Sort detections by x-coordinate (left to right)
            2. Compute gaps between adjacent bounding boxes
            3. Flag gaps exceeding min_gap_px threshold
        """
        pass
```

---

#### Contract: `core/classifier.py`

```python
# src/shelf_monitor/core/classifier.py

from typing import List
from pathlib import Path
from .detector import Detection  # Reuse Detection dataclass

class SKUClassifier:
    """
    Classifies detected products to SKU level.
    Implements Challenge 2 (Product Recognition).
    """
    
    def __init__(self, model_path: Path, confidence_threshold: float = 0.5) -> None:
        """
        Initialize classifier with trained model.
        
        Args:
            model_path: Path to YOLOv8 model weights (.pt file)
            confidence_threshold: Minimum confidence for valid detection
        """
        pass
    
    def classify_products(self, image_path: Path) -> List[Detection]:
        """
        Detect and classify products to SKU level.
        
        Args:
            image_path: Path to shelf image
            
        Returns:
            List of Detection objects with SKU labels
            
        Raises:
            ValueError: If model_path not found or image invalid
            RuntimeError: If inference fails
        """
        pass
    
    def evaluate_model(self, test_images: List[Path], ground_truth: List[List[Detection]]) -> dict:
        """
        Compute mAP@0.5 and classification accuracy on test set.
        
        Args:
            test_images: List of test image paths
            ground_truth: List of ground truth Detection lists (same order as test_images)
            
        Returns:
            dict with keys: 'map@0.5', 'accuracy', 'precision', 'recall'
        """
        pass
```

---

#### Contract: `core/stock_analyzer.py`

```python
# src/shelf_monitor/core/stock_analyzer.py

from typing import List, Dict
from dataclasses import dataclass
from .detector import Detection

@dataclass(frozen=True)
class ProductCount:
    """Stock count per SKU."""
    sku: str
    count: int
    estimated_depth: int
    total_estimate: int

class StockAnalyzer:
    """
    Estimates stock levels from detections.
    Implements Challenge 3 (Stock Level Estimation).
    """
    
    def count_products(self, detections: List[Detection]) -> Dict[str, ProductCount]:
        """
        Count products per SKU from detection results.
        
        Args:
            detections: List of Detection objects from SKUClassifier
            
        Returns:
            Dict mapping SKU to ProductCount object
            
        Algorithm:
            1. Group detections by SKU label
            2. Count occurrences per SKU
            3. Estimate depth (simple heuristic: depth=1 for Phase 1)
        """
        pass
    
    def estimate_depth(self, detections: List[Detection], sku: str) -> int:
        """
        Estimate shelf depth for given SKU (Phase 2+ enhancement).
        
        Args:
            detections: Filtered detections for specific SKU
            sku: SKU identifier
            
        Returns:
            Estimated number of rows (1-3)
            
        Heuristic (Phase 1): Always return 1 (front-facing only)
        Heuristic (Phase 2): Analyze bbox heights for stacking patterns
        """
        pass
```

---

#### Contract: `core/ocr.py`

```python
# src/shelf_monitor/core/ocr.py

from typing import List, Optional
from pathlib import Path
from dataclasses import dataclass

@dataclass(frozen=True)
class PriceTag:
    """Extracted price information."""
    bbox: tuple  # (x, y, width, height)
    text: str  # Raw OCR text
    price: Optional[float]  # Parsed price value
    currency: str  # $, €, £
    confidence: float  # OCR confidence

class PriceOCR:
    """
    Extracts and verifies price tags using Azure Document Intelligence.
    Implements Challenge 4 (Price Tag Verification).
    """
    
    def __init__(self, endpoint: str, key: str) -> None:
        """
        Initialize OCR with Azure Document Intelligence credentials.
        
        Args:
            endpoint: Azure Document Intelligence endpoint
            key: Azure Document Intelligence key
        """
        pass
    
    def extract_prices(self, image_path: Path) -> List[PriceTag]:
        """
        Extract price tags from shelf image using pre-trained OCR.
        
        Args:
            image_path: Path to shelf image with visible price tags
            
        Returns:
            List of PriceTag objects with extracted prices
            
        Raises:
            ValueError: If image invalid
            AzureError: If API call fails (retries 3x)
            QuotaExceededError: If 500 pages/month F0 limit exceeded
        """
        pass
    
    def parse_price(self, text: str) -> tuple[Optional[float], str]:
        """
        Parse price value and currency from OCR text.
        
        Args:
            text: Raw OCR text (e.g., "$19.99", "€12,50")
            
        Returns:
            Tuple of (price_value, currency_symbol)
            Returns (None, "") if parsing fails
            
        Algorithm:
            1. Regex match for currency symbols and numbers
            2. Handle multiple formats ($X.XX, €X,XX, £X.XX)
            3. Return None if no valid price pattern found
        """
        pass
```

---

#### Contract: `api/routers/products.py` (FastAPI Endpoints)

```python
# src/shelf_monitor/api/routers/products.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ...database.schemas import ProductCreate, ProductUpdate, ProductResponse
from ...database.crud import create_product, get_products, get_product_by_sku, update_product, delete_product
from ..dependencies import get_db

router = APIRouter(prefix="/api/v1/products", tags=["products"])

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product_endpoint(product: ProductCreate, db: Session = Depends(get_db)):
    """
    Create new product in catalog.
    
    Args:
        product: ProductCreate schema with sku, name, category_id, expected_price
        db: Database session (injected)
        
    Returns:
        ProductResponse with created product details
        
    Raises:
        HTTP 400: If SKU already exists
        HTTP 404: If category_id invalid
    """
    pass

@router.get("/", response_model=List[ProductResponse])
def list_products_endpoint(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    List all products with pagination.
    
    Query Params:
        skip: Offset for pagination (default 0)
        limit: Max results to return (default 100, max 1000)
        
    Returns:
        List of ProductResponse objects
    """
    pass

@router.get("/{sku}", response_model=ProductResponse)
def get_product_endpoint(sku: str, db: Session = Depends(get_db)):
    """
    Get product by SKU.
    
    Args:
        sku: Product SKU identifier
        
    Returns:
        ProductResponse with product details
        
    Raises:
        HTTP 404: If SKU not found
    """
    pass

@router.put("/{sku}", response_model=ProductResponse)
def update_product_endpoint(sku: str, product: ProductUpdate, db: Session = Depends(get_db)):
    """
    Update product by SKU.
    
    Args:
        sku: Product SKU identifier
        product: ProductUpdate schema with fields to update
        
    Returns:
        ProductResponse with updated product
        
    Raises:
        HTTP 404: If SKU not found
    """
    pass

@router.delete("/{sku}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_endpoint(sku: str, db: Session = Depends(get_db)):
    """
    Delete product by SKU.
    
    Args:
        sku: Product SKU identifier
        
    Raises:
        HTTP 404: If SKU not found
    """
    pass
```

---

#### Contract: `api/routers/analysis.py` (Analysis Job Endpoints)

```python
# src/shelf_monitor/api/routers/analysis.py

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ...database.schemas import AnalysisJobResponse, DetectionResponse
from ...database.crud import create_analysis_job, get_analysis_job, get_analysis_jobs
from ..dependencies import get_db
from ...core.detector import ProductDetector
from ...core.classifier import SKUClassifier

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])

@router.post("/detect", response_model=AnalysisJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_detection_job(
    image: UploadFile = File(...), 
    challenge_type: str = "PRODUCT_RECOGNITION",
    db: Session = Depends(get_db)
):
    """
    Submit image for analysis (async processing).
    
    Args:
        image: Uploaded shelf image (JPEG/PNG)
        challenge_type: One of OOS_DETECTION, PRODUCT_RECOGNITION, STOCK_ESTIMATION, PRICE_VERIFICATION
        db: Database session
        
    Returns:
        AnalysisJobResponse with job_id and status=PENDING
        
    Process:
        1. Save uploaded image to data/uploads/
        2. Create AnalysisJob record with status=PENDING
        3. Queue background task for ML processing
        4. Return job_id immediately (202 Accepted)
    """
    pass

@router.get("/{job_id}", response_model=AnalysisJobResponse)
def get_analysis_job_status(job_id: int, db: Session = Depends(get_db)):
    """
    Get analysis job status and results.
    
    Args:
        job_id: AnalysisJob ID
        
    Returns:
        AnalysisJobResponse with status, detections (if completed)
        
    Raises:
        HTTP 404: If job_id not found
    """
    pass

@router.get("/{job_id}/detections", response_model=List[DetectionResponse])
def get_analysis_detections(job_id: int, db: Session = Depends(get_db)):
    """
    Get all detections for completed analysis job.
    
    Args:
        job_id: AnalysisJob ID
        
    Returns:
        List of DetectionResponse objects
        
    Raises:
        HTTP 404: If job_id not found
        HTTP 400: If job not completed (status != COMPLETED)
    """
    pass
```

---

#### Contract: `database/crud.py` (Database Operations)

```python
# src/shelf_monitor/database/crud.py

from sqlalchemy.orm import Session
from typing import List, Optional
from .models import Product, Category, AnalysisJob, Detection, PriceHistory
from .schemas import ProductCreate, ProductUpdate, AnalysisJobCreate

def create_product(db: Session, product: ProductCreate) -> Product:
    """Create new product in database."""
    pass

def get_products(db: Session, skip: int = 0, limit: int = 100) -> List[Product]:
    """Get all products with pagination."""
    pass

def get_product_by_sku(db: Session, sku: str) -> Optional[Product]:
    """Get product by SKU."""
    pass

def update_product(db: Session, sku: str, product: ProductUpdate) -> Optional[Product]:
    """Update product by SKU."""
    pass

def delete_product(db: Session, sku: str) -> bool:
    """Delete product by SKU. Returns True if deleted, False if not found."""
    pass

def create_analysis_job(db: Session, job: AnalysisJobCreate) -> AnalysisJob:
    """Create new analysis job."""
    pass

def get_analysis_job(db: Session, job_id: int) -> Optional[AnalysisJob]:
    """Get analysis job by ID with detections."""
    pass

def create_detection(db: Session, analysis_job_id: int, detection_data: dict) -> Detection:
    """Create detection record linked to analysis job."""
    pass

def get_detections_by_job(db: Session, job_id: int) -> List[Detection]:
    """Get all detections for analysis job."""
    pass

def create_price_history(db: Session, price_data: dict) -> PriceHistory:
    """Record price observation."""
    pass

def get_price_history(db: Session, sku: str, limit: int = 100) -> List[PriceHistory]:
    """Get price history for SKU."""
    pass
```

---

### D3: Quickstart Guide

**Output File**: `.specify/plans/quickstart.md`

**Content Structure**:

```markdown
# Quickstart Guide - Retail Shelf Monitoring

## Prerequisites
- Python 3.10+ installed
- Python 3.10+ (includes SQLite3 built-in)
- Azure subscription (free tier)
- 8GB+ RAM (16GB recommended)
- Optional: NVIDIA GPU with CUDA for faster training

## Installation (20 minutes)

### 1. Clone Repository
\`\`\`bash
git clone https://github.com/ducnguyenhuu/DucNguyen_LearningSpace.git
cd retail-shelf-monitoring
\`\`\`

### 2. Create Virtual Environment
\`\`\`bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\\Scripts\\activate
\`\`\`

### 3. Install Dependencies
\`\`\`bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For testing
\`\`\`

### 4. Configure Environment Variables
\`\`\`bash
cp .env.example .env
# Edit .env with your Azure credentials and database connection
\`\`\`

Example `.env`:
\`\`\`env
# Database
DATABASE_URL=sqlite:///data/retail_shelf_monitoring.db

# Azure Custom Vision
CUSTOM_VISION_TRAINING_KEY=your_training_key
CUSTOM_VISION_PREDICTION_KEY=your_prediction_key
CUSTOM_VISION_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
CUSTOM_VISION_PROJECT_ID=your_project_id

# Azure Document Intelligence
DOCUMENT_INTELLIGENCE_KEY=your_key
DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-resource.cognitiveservices.azure.com/
\`\`\`

## Database Setup (5 minutes)

### 1. Create Database Directory
\`\`\`bash
# Create data directory for SQLite database
mkdir -p data
\`\`\`

Note: SQLite requires no installation or server setup. The database file will be created automatically when you run the initialization script.

### 2. Run Migrations
\`\`\`bash
# Initialize Alembic (creates tables)
python scripts/init_database.py

# Seed product catalog from dataset annotations
python scripts/seed_products.py --dataset data/raw/SKU110K
\`\`\`

### 3. Verify Database
\`\`\`bash
# Connect to SQLite database
sqlite3 data/retail_shelf_monitoring.db

# List tables (in SQLite shell)
.tables

# Check products
SELECT COUNT(*) FROM products;

# Exit SQLite shell
.quit
\`\`\`

## Azure Setup (30 minutes)

### 1. Create Azure Resources
Follow `docs/guides/azure_setup.md` for detailed instructions:
- Create resource group: `rg-retail-shelf-monitoring`
- Provision Custom Vision (F0 free tier)
- Provision Document Intelligence (F0 free tier)
- Optional: Create Storage Account

### 2. Get API Keys
- Custom Vision: Copy Training Key, Prediction Key, Endpoint
- Document Intelligence: Copy Key, Endpoint
- Update `.env` file (see Installation step 4)

## Download Dataset (1 hour)

\`\`\`bash
python scripts/download_dataset.py --dataset SKU110K --output data/raw/
python scripts/prepare_data.py --input data/raw/SKU110K --output data/processed/

# Seed product catalog from dataset
python scripts/seed_products.py --dataset data/raw/SKU110K
\`\`\`

## Start FastAPI Backend (Development Mode)

\`\`\`bash
# Run FastAPI with auto-reload
uvicorn src.shelf_monitor.api.main:app --reload --host 0.0.0.0 --port 8000

# Test health endpoint
curl http://localhost:8000/api/v1/health

# View interactive API docs
open http://localhost:8000/docs
\`\`\`

Expected output:
- API running at `http://localhost:8000`
- Swagger UI available at `/docs`
- ReDoc available at `/redoc`

## Run Challenge 1: Out-of-Stock Detection (Week 3-4)

### 1. Ensure Backend Running
\`\`\`bash
# Terminal 1: FastAPI backend
uvicorn src.shelf_monitor.api.main:app --reload
\`\`\`

### 2. Open Notebook
\`\`\`bash
# Terminal 2: Jupyter
jupyter notebook notebooks/01_out_of_stock_detection.ipynb
\`\`\`

### 3. Follow Notebook Steps
- **Section 1**: Upload training images to Custom Vision via API
- **Section 2**: Train model (10 iterations available in F0)
- **Section 3**: Submit analysis job via POST /api/v1/analysis/detect
- **Section 4**: Poll job status, retrieve detections from database
- **Section 5**: Visualize gap regions and evaluate metrics

### 4. Expected Output
- Trained Custom Vision model (saved to Azure)
- AnalysisJob records in database (status: COMPLETED)
- Detection records linked to analysis job
- Visualizations in notebook (bounding boxes, gap regions)
- Metrics: Precision >90%, Recall >85%

## Explore API Endpoints

\`\`\`bash
# List all products
curl http://localhost:8000/api/v1/products

# Create product
curl -X POST http://localhost:8000/api/v1/products \\
  -H "Content-Type: application/json" \\
  -d '{"sku":"test_sku","name":"Test Product","category_id":1,"expected_price":9.99}'

# Submit analysis
curl -X POST http://localhost:8000/api/v1/analysis/detect \\
  -F "image=@data/test/shelf_001.jpg" \\
  -F "challenge_type=PRODUCT_RECOGNITION"

# Get analysis results
curl http://localhost:8000/api/v1/analysis/{job_id}
\`\`\`

## Next Steps
- Proceed to Challenge 2 (Product Recognition) in Week 5-6
- Read `docs/guides/challenge_2_product_recognition.md`
- Train YOLOv8 model and compare with Custom Vision
- Explore database queries: `docs/guides/database_design.md`
- Learn API development: `docs/guides/api_development.md`
\`\`\`

---

## Troubleshooting

**Issue**: Azure API returns 429 (Quota Exceeded)
**Fix**: Check monthly limits (10K predictions for Custom Vision F0). Wait until next month or upgrade tier.

**Issue**: Dataset download fails
**Fix**: Ensure internet connection stable. Use `wget -c` for resume capability.

**Issue**: Out of memory during YOLO training
**Fix**: Reduce batch size from 16 to 8 or 4. Or use CPU training (slower but works).

**Issue**: Database connection error "FATAL: database 'retail_shelf_monitoring' does not exist"
**Fix**: Run `createdb retail_shelf_monitoring` or `python scripts/init_database.py`

**Issue**: API returns 500 error "no module named 'src'"
**Fix**: Install package in editable mode: `pip install -e .`

**Issue**: Alembic migration fails "relation 'products' already exists"
**Fix**: Drop database and recreate: `dropdb retail_shelf_monitoring && createdb retail_shelf_monitoring && python scripts/init_database.py`
```

---

## Phase 1 Completion Checklist

Before proceeding to Phase 2 (implementation tasks):

- [ ] `research.md` complete with all 8 decisions documented (R1-R8 including database and API)
- [ ] `data-model.md` defines 5 database tables + 3 dataclasses (Product, Category, AnalysisJob, Detection, PriceHistory + GapRegion, ProductCount, PriceTag)
- [ ] Contracts defined for 4 ML core modules (detector.py, classifier.py, stock_analyzer.py, ocr.py)
- [ ] Contracts defined for API routers (products.py, analysis.py, detections.py, health.py)
- [ ] CRUD operations defined (database/crud.py)
- [ ] OpenAPI spec generated (api-spec.yaml) - can be auto-generated from FastAPI
- [ ] `quickstart.md` provides installation with database setup and API startup
- [ ] Constitution Check re-evaluated (no new violations introduced beyond justified database/API addition)
- [ ] All NEEDS CLARIFICATION from Technical Context resolved

**Gate**: ✅ Once checklist complete, proceed to `/speckit.tasks` command to generate detailed week-by-week implementation tasks (now includes database schema, API endpoints, and integration).

---

## Notes for Implementation

1. **Sequential Implementation**: Complete Challenge 1 Phase 1 fully (including database persistence and API endpoints) before starting Challenge 2. Document as you go.

2. **Database-First Approach**: Set up database schema and seed product catalog BEFORE implementing ML challenges. This provides realistic data for testing.

3. **API Development Parallel to ML**: Implement API endpoints alongside ML modules. For each challenge, create both the core ML logic AND the corresponding API endpoint.

4. **Azure Quota Monitoring**: Log API call counts to avoid surprises. Set up budget alerts ($5 threshold recommended).

5. **Educational Documentation**: Write guide for each challenge AND infrastructure component (database design, API development) immediately after implementation.

6. **Testing Pragmatism**: 
   - Unit tests: Pure Python logic (gap detection, counting, parsing, CRUD operations)
   - Integration tests: API endpoints with test database (SQLite in-memory)
   - Mock: Azure API calls only

7. **Phase 1 First**: Resist urge to optimize prematurely. Get working implementation (ML + API + DB), then iterate.

8. **Git Commits**: Commit after each major milestone (database setup, Challenge 1 ML + API, Challenge 2 ML + API, etc.). Use descriptive messages.

9. **Notebook Best Practices**: Include markdown explanations, visualizations, educational comments, AND examples of calling the REST API from notebooks.

10. **Database Migrations**: Use Alembic for all schema changes. Never manually ALTER tables. Teach "why migrations matter" in documentation.

---

**Status**: ✅ Plan complete. Ready for Phase 0 (research) execution.

**Next Command**: Proceed to generate `research.md` by dispatching research agents for tasks R1-R6.
