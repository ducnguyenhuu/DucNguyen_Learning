# Research Findings - Retail Shelf Monitoring

**Date**: December 10, 2025  
**Status**: Phase 0 Complete  
**Purpose**: Document technology decisions and best practices for full-stack implementation

---

## Decision R1: Dataset Management Strategy

### Chosen Solution
Use **full SKU-110K dataset (11,762 images)** for single-class YOLO training. No subsetting needed.

### Rationale
- **Single Class**: Dataset already has "object" annotations (no multi-class labeling)
- **No Cloud Limits**: Training locally, no Azure Custom Vision 5K image limit
- **Maximum Learning Data**: More training data = better YOLO performance
- **Storage**: Local filesystem sufficient (~5GB total)

### Implementation Details
**Preprocessing Pipeline**:
```python
# scripts/prepare_data.py workflow (COMPLETED IN T017)
1. Download SKU-110K from GitHub (11,762 images, CSV annotations)
2. Convert CSV → YOLO format (txt files: class x_center y_center width height)
3. Split using original SKU-110K splits: train (8,219) / val (588) / test (2,936)
4. Validate: Check for corrupt images, missing annotations
```

**Directory Structure**:
```
data/
├── raw/SKU110K/SKU110K_fixed/     # Original download
│   ├── images/                     # 11,762 JPG files
│   └── annotations/                # 3 CSV files (train/val/test)
└── processed/SKU110K_yolo/         # YOLO format (COMPLETED)
    ├── images/
    │   ├── train/ (8,219 images)
    │   ├── val/ (588 images)
    │   └── test/ (2,936 images)
    ├── labels/
    │   ├── train/ (8,219 .txt files)
    │   ├── val/ (588 .txt files)
    │   └── test/ (2,936 .txt files)
    └── data.yaml  # YOLO training config
```

**Data Augmentation**:
- **Built-in**: YOLO auto-applies mosaic, mixup, HSV jitter
- **No custom augmentation needed** for Phase 1

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| **Subset for Azure Custom Vision** | Not using Azure, no cloud limits |
| **Cloud-only storage (Azure Blob)** | Adds complexity and cost; local storage sufficient |
| **Use Grocery Store dataset** | Smaller (5,125 images); SKU-110K is larger and better |
| **Manual labeling for multi-class** | Too time-consuming (50-100 images); single-class is simpler |

### Tools & Commands
```bash
# Already completed in T017
python3 scripts/prepare_data.py  # Converts SKU-110K to YOLO format

# Validate dataset
ls data/processed/SKU110K_yolo/images/train | wc -l  # Should be 8219
ls data/processed/SKU110K_yolo/labels/train | wc -l  # Should be 8219
```

---

## Decision R2: Single-Class YOLO Strategy

### Chosen Solution
Train **one YOLOv8s model** with single class "object" to serve both Challenge 1 (gap detection) and Challenge 2 (object counting).

### Rationale
- **Simplicity**: Single model, single class, no manual labeling required
- **SKU-110K Ready**: Dataset already has "object" annotations for all 11,762 images
- **Dual Purpose**: Same detections used for gap analysis AND counting
- **Cost**: $0 (no cloud services, local training only)
- **Learning Focus**: Deep dive into YOLO training, inference, and post-processing

### Implementation Strategy

**Single YOLO Model**:
```yaml
Goal: Detect all objects on retail shelves (single "object" class)
Dataset: SKU-110K full dataset (8,219 train, 588 val, 2,936 test)
Training Time: 2-3 hours (GPU), 8-10 hours (CPU)
Evaluation: Precision >90%, Recall >85%, mAP@0.5 >85%
```

**Challenge 1: Gap Detection**:
```python
# Use YOLO detections to find empty spaces
detections = model.predict(image)  # Get bounding boxes
gaps = analyze_gaps(detections)     # Geometric analysis
```

**Challenge 2: Object Counting**:
```python
# Simply count detections
detections = model.predict(image)
count = len(detections)  # Total objects
```

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| **Multi-class YOLO** | Requires manual labeling (50-100 images × 10-15 classes = 2-3 hours work) |
| **Azure Custom Vision** | Adds cost, cloud dependency, quota limits; not needed for learning goals |
| **Pre-trained COCO model** | Generic classes (bottle, cup) don't match retail products well |
| **Separate models per challenge** | Unnecessary complexity; one model serves both use cases |

### Tools & Commands
```bash
# Train YOLO on SKU-110K
yolo train data=data/processed/SKU110K_yolo/data.yaml \
  model=yolov8s.pt epochs=50 imgsz=640 batch=16

# Inference
yolo predict model=models/best.pt source=test_image.jpg
```

---

## Decision R3: YOLOv8 Training Configuration

### Chosen Solution
Use **YOLOv8s (small)** model with pretrained COCO weights, train for **50 epochs**, batch size **16** on GPU (M1/M2 or NVIDIA 6GB+ VRAM).

### Rationale
- **Model Size**: YOLOv8s balances accuracy (mAP ~45% COCO) and speed (~10 FPS on consumer GPU)
- **Hardware**: Most junior developers have M1/M2 Mac or entry-level NVIDIA GPU (GTX 1060/RTX 3060)
- **Training Time**: 2-4 hours reasonable for learning project (vs 6-8h for YOLOv8m)
- **Transfer Learning**: COCO pretrained weights accelerate convergence (vs random initialization)

### Training Configuration

```yaml
Model: YOLOv8s
Input Size: 640x640 (YOLO standard)
Batch Size: 16 for training (GPU), 4 for training (CPU fallback), 1 for inference latency measurement
Epochs: 50
Learning Rate: 0.01 (default)
Optimizer: SGD with momentum 0.937
Augmentation: Mosaic, MixUp, HSV jitter (Ultralytics defaults)
Pretrained: COCO weights (80 classes)
Hardware:
  - Preferred: M1/M2 Mac (MPS backend) or NVIDIA GPU (6GB+ VRAM)
  - Fallback: CPU (8-10 hours training time)
Dataset: Full SKU-110K (8,233 train images)
```

**Expected Performance** (Challenge 2):
- mAP@0.5: 85-90% on retail shelf images
- Inference: 10-15 FPS (GPU), 2-3 FPS (CPU)
- Model Size: ~22MB (.pt file)

### Hardware Requirements

| Hardware | VRAM | Batch Size | Training Time | Inference FPS |
|----------|------|------------|---------------|---------------|
| **M1/M2 Mac** | Unified 8GB+ | 16 | 2-3 hours | 12-15 |
| **NVIDIA RTX 3060** | 12GB | 16 | 2-3 hours | 15-20 |
| **NVIDIA GTX 1060** | 6GB | 8 | 3-4 hours | 10-12 |
| **CPU (8-core)** | System RAM | 4 | 8-10 hours | 2-3 |

### Training Script
```python
# models/yolo.py or notebooks/02_product_recognition.ipynb

from ultralytics import YOLO

# Load pretrained model
model = YOLO('yolov8s.pt')  # Downloads automatically

# Train
results = model.train(
    data='data/processed/yolo/data.yaml',  # Dataset config
    epochs=50,
    imgsz=640,
    batch=16,  # Adjust based on GPU memory
    device='mps',  # 'mps' (M1/M2), '0' (NVIDIA), 'cpu'
    project='models/runs',
    name='sku_recognition',
    pretrained=True,
    patience=10,  # Early stopping
    save_period=10,  # Save checkpoint every 10 epochs
    cache=True,  # Cache images in RAM for faster training
)

# Evaluate
metrics = model.val()
print(f"mAP@0.5: {metrics.box.map50:.3f}")
```

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| **YOLOv8n (nano)** | Faster (20 FPS) but lower accuracy (mAP ~40%); may not hit 85% target |
| **YOLOv8m (medium)** | Higher accuracy (mAP ~50%) but slower (6 FPS) and 2x training time; overkill for learning |
| **YOLOv5** | Older architecture; YOLOv8 has better docs and performance |
| **Faster R-CNN / Mask R-CNN** | Slower inference, more complex; YOLO better for learning |
| **Train from scratch** | Requires 100+ epochs; pretrained weights much faster |

### Data Configuration File
```yaml
# data/processed/yolo/data.yaml

path: /absolute/path/to/data/processed/yolo
train: train/images
val: val/images
test: test/images

nc: 81  # Number of product classes (adjust based on SKU-110K subset)
names: ['product_1', 'product_2', ...]  # Class names from dataset
```

---

## Decision R4: Azure Document Intelligence OCR Strategy

### Chosen Solution
Use **Azure Document Intelligence Read API** (prebuilt model) with **exponential backoff retry** for rate limiting, parse prices via **regex**, require **confidence >0.8**.

### Rationale
- **No Training Needed**: Prebuilt Read API works out-of-box for printed text
- **Free Tier**: 500 pages/month sufficient for Challenge 4 testing (~100-200 images)
- **Rate Limiting**: 15 requests/min on F0 - need retry logic
- **Simple Approach**: Regex parsing adequate for standard price formats ($X.XX, €X,XX)

### API Selection

**Read API vs Layout API**:
```
Read API (Chosen):
  ✅ Extracts text with bounding boxes
  ✅ Simple output format
  ✅ Sufficient for price tags
  ✅ Faster processing (~2-3s per image)
  
Layout API:
  ❌ Overkill (tables, forms, paragraphs)
  ❌ More complex output
  ❌ Slower processing (~5-7s)
```

### Implementation Strategy

**OCR Pipeline** (Challenge 4):
```python
# core/ocr.py

from azure.ai.formrecognizer import DocumentAnalysisClient
import re
from typing import Optional, Tuple

class PriceOCR:
    def __init__(self, endpoint: str, key: str):
        self.client = DocumentAnalysisClient(endpoint, AzureKeyCredential(key))
        self.confidence_threshold = 0.8
        
    def extract_prices(self, image_path: Path) -> List[PriceTag]:
        """Extract price tags using Read API."""
        # Retry logic with exponential backoff
        for attempt in range(3):
            try:
                with open(image_path, 'rb') as f:
                    poller = self.client.begin_analyze_document(
                        "prebuilt-read", document=f
                    )
                result = poller.result()
                break
            except HttpResponseError as e:
                if e.status_code == 429:  # Rate limit
                    wait_time = 2 ** attempt  # 1s, 2s, 4s
                    logging.warning(f"Rate limited. Retry in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise
        
        # Parse prices from text
        prices = []
        for page in result.pages:
            for line in page.lines:
                if line.confidence > self.confidence_threshold:
                    price, currency = self.parse_price(line.content)
                    if price:
                        prices.append(PriceTag(
                            bbox=(line.bounding_box[0], line.bounding_box[1],
                                  line.bounding_box[4], line.bounding_box[5]),
                            text=line.content,
                            price=price,
                            currency=currency,
                            confidence=line.confidence
                        ))
        return prices
    
    def parse_price(self, text: str) -> Tuple[Optional[float], str]:
        """Parse price value and currency from OCR text."""
        # Regex patterns for common formats
        patterns = [
            r'\$\s*(\d+\.?\d*)',      # $19.99
            r'€\s*(\d+,?\d*)',        # €19,99
            r'£\s*(\d+\.?\d*)',       # £19.99
            r'(\d+\.?\d*)\s*USD',     # 19.99 USD
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                price_str = match.group(1).replace(',', '.')
                return float(price_str), self._extract_currency(text)
        
        return None, ""
```

### Price Parsing Strategy

**Supported Formats**:
- `$19.99` → 19.99, USD
- `€19,99` → 19.99, EUR
- `£19.99` → 19.99, GBP
- `19.99 USD` → 19.99, USD
- `$2.50 / each` → 2.50, USD (extract first number)

**Confidence Thresholding**:
- Require OCR confidence >0.8 for accepted prices
- Log low-confidence detections for manual review
- Fall back to "price not detected" if no high-confidence match

### Rate Limiting Handling

**Exponential Backoff**:
```python
def retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except HttpResponseError as e:
            if e.status_code == 429:
                wait = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait)
            else:
                raise
    raise Exception("Max retries exceeded")
```

**Quota Monitoring**:
- Log each API call to track monthly usage
- Warn at 80% (400/500 pages)
- Educational error message when quota exhausted

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| **Layout API** | Overkill for simple price tags; slower and more complex |
| **Custom Vision OCR** | Requires training data; prebuilt Read API sufficient |
| **Open-source OCR (Tesseract)** | Misses Azure learning objective; lower accuracy on real images |
| **GPT-4 Vision** | Expensive ($0.01/image); overkill for price extraction |
| **Fuzzy matching fallback** | Adds complexity; regex sufficient for Phase 1 |

---

## Decision R5: Error Handling & Resilience Patterns

### Chosen Solution
Implement **3-attempt retry with exponential backoff** (1s, 2s, 4s) for Azure APIs, **educational error messages** with "what + why + fix", **console logging** with DEBUG level.

### Rationale
- **Learning First**: Error messages teach concepts (quotas, rate limits, timeouts)
- **Simple Patterns**: Retry logic straightforward to understand and implement
- **Fail Fast**: After 3 attempts, surface error to user rather than infinite retry
- **Visibility**: Console logging shows intermediate steps for educational value

### Error Types & Strategies

| Error Type | HTTP Code | Retry | User Message | Recovery |
|------------|-----------|-------|--------------|----------|
| **Rate Limit** | 429 | Yes (3x) | "Azure API rate limited. Retrying... (X/3)" | Exponential backoff 1s→2s→4s |
| **Quota Exceeded** | 403 | No | "Custom Vision quota exceeded (10K/month). Upgrade tier or use YOLO." | Switch to local inference |
| **Authentication** | 401 | No | "Azure credentials invalid. Check .env file keys." | Verify API keys in .env |
| **Timeout** | - | Yes (3x) | "Request timed out (30s). Check internet connection." | Retry with backoff |
| **Server Error** | 500 | Yes (3x) | "Azure service unavailable. Retrying... (X/3)" | Exponential backoff |
| **Invalid Image** | - | No | "Invalid image: {path}. Must be JPEG/PNG, min 640x480." | Validate file locally |
| **Not Found** | 404 | No | "File not found: {path}. Check path and try again." | Verify file exists |

### Implementation

**Retry Decorator**:
```python
# utils/retry.py

import time
import logging
from functools import wraps
from typing import Type, Tuple

def retry_with_backoff(
    max_retries: int = 3,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    backoff_base: int = 2
):
    """Retry function with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        logging.error(f"{func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    
                    wait_time = backoff_base ** attempt
                    logging.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} failed. "
                        f"Retrying in {wait_time}s... Error: {e}"
                    )
                    time.sleep(wait_time)
            
        return wrapper
    return decorator
```

**Usage Example**:
```python
# services/azure_custom_vision.py

from azure.core.exceptions import HttpResponseError
from utils.retry import retry_with_backoff

class CustomVisionClient:
    
    @retry_with_backoff(max_retries=3, exceptions=(HttpResponseError,))
    def predict(self, image_path: Path):
        """Predict with automatic retry on failure."""
        with open(image_path, 'rb') as image:
            results = self.predictor.detect_image(
                self.project_id,
                self.iteration_name,
                image
            )
        return results
```

### Educational Error Messages

**Template**: `{WHAT} | {WHY} | {FIX}`

**Examples**:
```python
# Custom Vision quota
"Custom Vision quota exceeded (10,000 predictions/month). | "
"Free tier (F0) limits API calls. | "
"Wait until next month, upgrade to S0 ($2/month), or switch to local YOLO inference."

# Invalid image
"Invalid image format: sample.bmp. | "
"Custom Vision requires JPEG or PNG format. | "
"Convert image to JPEG/PNG using Pillow or GIMP."

# Authentication failure
"Azure authentication failed: Invalid API key. | "
"API key in .env may be incorrect or expired. | "
"1. Check CUSTOM_VISION_PREDICTION_KEY in .env matches Azure Portal. "
"2. Regenerate key in Azure Portal if needed."
```

### Logging Strategy

**Console Logging** (Phase 1):
```python
# utils/logging.py

import logging

def setup_logging(level=logging.DEBUG):
    """Configure structured console logging."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Reduce Azure SDK noise
    logging.getLogger('azure').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
```

**Log Levels**:
- `DEBUG`: Intermediate steps (bbox coords, confidence scores)
- `INFO`: Major milestones (training started, model saved)
- `WARNING`: Recoverable issues (retry attempts, quota warnings)
- `ERROR`: Failures after retries

**File Logging** (Phase 4):
```python
# Add file handler for persistent logs
file_handler = logging.FileHandler('logs/app.log')
file_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(file_handler)
```

### Quota Monitoring

```python
# utils/quota_monitor.py

class QuotaMonitor:
    def __init__(self, service: str, monthly_limit: int):
        self.service = service
        self.monthly_limit = monthly_limit
        self.usage_count = 0
        
    def increment(self):
        """Track API usage."""
        self.usage_count += 1
        percentage = (self.usage_count / self.monthly_limit) * 100
        
        if percentage >= 80:
            logging.warning(
                f"{self.service} quota at {self.usage_count}/{self.monthly_limit} "
                f"({percentage:.1f}%). Consider conservation or upgrade."
            )
    
    def reset_monthly(self):
        """Reset counter (call via scheduler or manual)."""
        self.usage_count = 0
        logging.info(f"{self.service} quota counter reset.")
```

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| **Infinite retry** | Could hang indefinitely; fail fast better for learning |
| **Linear backoff** | Less effective than exponential for rate limiting |
| **Silent failures** | Hides errors from learners; educational value in visibility |
| **Complex error codes** | Overwhelming for juniors; human-readable messages better |
| **File logging only** | Console output essential for Jupyter notebook feedback |

---

## Decision R6: Testing Strategy for Learning Project

### Chosen Solution
**Unit tests** for pure Python logic (gap detection, counting, parsing, CRUD), **integration tests** for API endpoints (FastAPI TestClient + SQLite in-memory), **mock Azure SDKs**, target **>70% coverage** (not strict).

### Rationale
- **Educational Value**: Testing teaches good practices without overwhelming
- **Pragmatic Scope**: Focus on testable logic, skip Azure API integration tests (mock instead)
- **Fast Feedback**: In-memory SQLite makes tests run in seconds
- **Learning Goal**: Understand pytest, mocking, test fixtures

### Testing Scope

**Unit Tests** (Core Logic):
```
✅ Test:
  - Gap detection algorithm (core/detector.py::detect_gaps)
  - Product counting (core/stock_analyzer.py::count_products)
  - Price parsing regex (core/ocr.py::parse_price)
  - CRUD operations (database/crud.py)
  - Image validation (utils/image.py)
  
❌ Don't Test:
  - Azure API calls (too slow, costs money)
  - YOLO model training (long-running)
  - Database queries (covered by integration tests)
  - Jupyter notebooks (manual testing)
```

**Integration Tests** (API + Database):
```
✅ Test:
  - API endpoints (POST /products, GET /analysis/{id})
  - Database transactions (create product → query → delete)
  - End-to-end workflows (upload image → create job → get results)
  
❌ Don't Test:
  - ML inference in API (mock detector/classifier)
  - Real PostgreSQL (use SQLite in-memory)
  - Background jobs (Phase 4 feature)
```

### Test Structure

**pytest Configuration** (`pytest.ini`):
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    --verbose
    --cov=src/shelf_monitor
    --cov-report=term-missing
    --cov-report=html
    -p no:warnings
```

**Directory Layout**:
```
tests/
├── unit/
│   ├── test_detector.py         # Gap detection logic
│   ├── test_classifier.py       # (Future) Classification logic
│   ├── test_stock_analyzer.py   # Product counting
│   ├── test_ocr.py              # Price parsing
│   └── test_crud.py             # Database CRUD
├── integration/
│   ├── test_api_products.py     # Product API endpoints
│   ├── test_api_analysis.py     # Analysis API endpoints
│   └── test_database_crud.py    # Database integration
└── conftest.py                  # Shared fixtures
```

### Mocking Strategy

**Mock Azure SDKs** (avoid real API calls):
```python
# tests/unit/test_detector.py

import pytest
from unittest.mock import Mock, patch
from shelf_monitor.core.detector import ProductDetector

@pytest.fixture
def mock_custom_vision():
    """Mock Azure Custom Vision predictor."""
    with patch('azure.cognitiveservices.vision.customvision.prediction.CustomVisionPredictionClient') as mock:
        predictor = Mock()
        predictor.detect_image.return_value = Mock(
            predictions=[
                Mock(bounding_box=Mock(left=100, top=50, width=80, height=120),
                     probability=0.95,
                     tag_name='product_1')
            ]
        )
        mock.return_value = predictor
        yield mock

def test_detect_products(mock_custom_vision, tmp_path):
    """Test product detection with mocked Azure API."""
    # Create dummy image
    image_path = tmp_path / "test.jpg"
    image_path.write_bytes(b'fake image data')
    
    detector = ProductDetector(endpoint="test", key="test")
    detections = detector.detect_products(image_path)
    
    assert len(detections) == 1
    assert detections[0].confidence == 0.95
    assert detections[0].label == 'product_1'
```

**FastAPI TestClient** (API testing):
```python
# tests/integration/test_api_products.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from shelf_monitor.api.main import app
from shelf_monitor.database.models import Base
from shelf_monitor.api.dependencies import get_db

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def test_db():
    """Create test database."""
    Base.metadata.create_all(bind=engine)
    yield TestingSessionLocal()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client(test_db):
    """FastAPI test client with test database."""
    def override_get_db():
        try:
            yield test_db
        finally:
            test_db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)

def test_create_product(client):
    """Test POST /products endpoint."""
    response = client.post(
        "/api/v1/products",
        json={
            "sku": "test_sku",
            "name": "Test Product",
            "category_id": 1,
            "expected_price": 9.99
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["sku"] == "test_sku"
    assert data["expected_price"] == 9.99
```

### Coverage Target

**>70% for core/ and api/** (not strict):
- Goal is understanding testing concepts, not 100% coverage
- Focus on critical logic (gap detection, counting, CRUD)
- Educational value > coverage percentage

**Run Coverage**:
```bash
pytest --cov=src/shelf_monitor --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Test Execution

**Local Development**:
```bash
# Run all tests
pytest

# Run specific file
pytest tests/unit/test_detector.py

# Run with coverage
pytest --cov=src/shelf_monitor --cov-report=term-missing

# Run fast (skip integration)
pytest tests/unit/
```

**Before Commit**:
```bash
# Run tests + linting
pytest && black src/ tests/ && flake8 src/ tests/
```

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| **Real Azure API tests** | Slow (network latency), costs money, rate limited; mocking better |
| **Real PostgreSQL for tests** | Slower than SQLite in-memory; requires setup; integration tests optional |
| **100% coverage target** | Overwhelming for learning project; diminishing returns above 70% |
| **No tests (notebooks only)** | Misses testing best practices; unit tests teach good habits |
| **E2E tests with Selenium** | Out of scope (no UI); API tests sufficient |

---

## Decision R7: Database Design Strategy

### Chosen Solution
**PostgreSQL 15+** with **5 normalized tables (3NF)**, **SQLAlchemy 2.0 ORM**, **Alembic migrations**, **indexed foreign keys**.

### Rationale
- **Production Database**: PostgreSQL teaches enterprise SQL (vs SQLite toy database)
- **Normalization**: 3NF eliminates redundancy, teaches data modeling concepts
- **ORM Benefits**: Pythonic interface, type safety, easier learning curve
- **Migrations**: Alembic teaches schema versioning (essential for real projects)
- **Learning Value**: Exposure to raw SQL in educational comments

### Schema Design

**5 Tables** (3rd Normal Form):

```sql
-- Table 1: categories
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

-- Table 2: products
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    expected_price DECIMAL(10, 2) NOT NULL CHECK (expected_price > 0),
    barcode VARCHAR(20),
    image_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table 3: analysis_jobs
CREATE TABLE analysis_jobs (
    id SERIAL PRIMARY KEY,
    image_path TEXT NOT NULL,
    challenge_type VARCHAR(50) NOT NULL CHECK (challenge_type IN (
        'OOS_DETECTION', 
        'PRODUCT_RECOGNITION', 
        'STOCK_ESTIMATION', 
        'PRICE_VERIFICATION'
    )),
    status VARCHAR(20) NOT NULL CHECK (status IN (
        'PENDING', 
        'PROCESSING', 
        'COMPLETED', 
        'FAILED'
    )),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

-- Table 4: detections
CREATE TABLE detections (
    id SERIAL PRIMARY KEY,
    analysis_job_id INTEGER NOT NULL REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    sku VARCHAR(100),  -- Soft FK to products (nullable for unknown products)
    bbox_x INTEGER NOT NULL CHECK (bbox_x >= 0),
    bbox_y INTEGER NOT NULL CHECK (bbox_y >= 0),
    bbox_width INTEGER NOT NULL CHECK (bbox_width > 0),
    bbox_height INTEGER NOT NULL CHECK (bbox_height > 0),
    confidence DECIMAL(4, 3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    label VARCHAR(100) NOT NULL
);

-- Table 5: price_history
CREATE TABLE price_history (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(100) NOT NULL REFERENCES products(sku),
    detected_price DECIMAL(10, 2) NOT NULL CHECK (detected_price > 0),
    expected_price DECIMAL(10, 2) NOT NULL,
    price_difference DECIMAL(10, 2) GENERATED ALWAYS AS (detected_price - expected_price) STORED,
    confidence DECIMAL(4, 3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    image_path TEXT NOT NULL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Indexes

**Performance Optimization**:
```sql
-- Primary keys (auto-indexed by PostgreSQL)
-- Foreign keys (indexed for JOIN performance)
CREATE INDEX idx_products_category_id ON products(category_id);
CREATE INDEX idx_detections_analysis_job_id ON detections(analysis_job_id);
CREATE INDEX idx_detections_sku ON detections(sku);
CREATE INDEX idx_price_history_sku ON price_history(sku);

-- Composite index for common queries
CREATE INDEX idx_detections_job_sku ON detections(analysis_job_id, sku);

-- Time-series queries
CREATE INDEX idx_price_history_detected_at ON price_history(detected_at DESC);
```

### SQLAlchemy ORM Models

**Example** (`database/models.py`):
```python
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, CheckConstraint, Text
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(100), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    expected_price = Column(Numeric(10, 2), nullable=False)
    barcode = Column(String(20))
    image_url = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    category = relationship("Category", back_populates="products")
    price_history = relationship("PriceHistory", back_populates="product")
    
    __table_args__ = (
        CheckConstraint('expected_price > 0', name='check_positive_price'),
    )

class Detection(Base):
    __tablename__ = 'detections'
    
    id = Column(Integer, primary_key=True)
    analysis_job_id = Column(Integer, ForeignKey('analysis_jobs.id', ondelete='CASCADE'), nullable=False)
    sku = Column(String(100))  # Soft FK
    bbox_x = Column(Integer, nullable=False)
    bbox_y = Column(Integer, nullable=False)
    bbox_width = Column(Integer, nullable=False)
    bbox_height = Column(Integer, nullable=False)
    confidence = Column(Numeric(4, 3), nullable=False)
    label = Column(String(100), nullable=False)
    
    # Relationships
    analysis_job = relationship("AnalysisJob", back_populates="detections")
    
    __table_args__ = (
        CheckConstraint('bbox_x >= 0', name='check_bbox_x'),
        CheckConstraint('bbox_width > 0', name='check_bbox_width'),
        CheckConstraint('confidence BETWEEN 0 AND 1', name='check_confidence'),
    )
```

### Migration Strategy

**Alembic Workflow**:
```bash
# Initialize Alembic
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Create products and categories tables"

# Review generated file in alembic/versions/

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

**Educational Comments** (in migration files):
```python
# alembic/versions/001_create_products.py

def upgrade():
    # Creates products table with foreign key to categories
    # 3NF: category_id reference eliminates category name duplication
    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sku', sa.String(length=100), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sku')
    )
    # Index improves JOIN performance (products ⋈ categories)
    op.create_index('idx_products_category_id', 'products', ['category_id'])
```

### Connection Management

**Session Management** (`database/session.py`):
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

SQLALCHEMY_DATABASE_URL = "postgresql://postgres:password@localhost:5432/retail_shelf_monitoring"

engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db_session():
    """Dependency for database session (context manager)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# FastAPI dependency
def get_db():
    """Dependency for FastAPI endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Sample Queries (Educational)

**Join Example** (products + categories):
```python
# ORM way
products = db.query(Product).join(Category).filter(Category.name == 'Beverages').all()

# Raw SQL equivalent (educational comment):
# SELECT products.* FROM products 
# JOIN categories ON products.category_id = categories.id 
# WHERE categories.name = 'Beverages';
```

**Aggregation Example** (stock count from detections):
```python
from sqlalchemy import func

# Count products per SKU from analysis job
stock_counts = (
    db.query(Detection.sku, func.count(Detection.id).label('count'))
    .filter(Detection.analysis_job_id == job_id)
    .group_by(Detection.sku)
    .all()
)

# Raw SQL:
# SELECT sku, COUNT(id) as count
# FROM detections
# WHERE analysis_job_id = 123
# GROUP BY sku;
```

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| **SQLite** | Not production database; want to learn PostgreSQL |
| **NoSQL (MongoDB)** | SQL explicitly requested for learning; relational data fits well |
| **Denormalized schema** | Defeats data modeling learning goal; violates 3NF |
| **Raw SQL only (no ORM)** | More verbose; ORM provides Pythonic interface + type safety |
| **Async SQLAlchemy** | Adds complexity; sync sufficient for Phase 1 |

---

## Decision R8: FastAPI Architecture Strategy

### Chosen Solution
**Router-based structure** (products, analysis, detections, health), **dependency injection** for database sessions (`Depends(get_db)`), **Pydantic schemas** for validation, **no authentication** in Phase 1.

### Rationale
- **Clean Separation**: Routers by domain match REST resource hierarchy
- **Dependency Injection**: FastAPI pattern for database session management
- **Type Safety**: Pydantic auto-validates request/response, generates OpenAPI docs
- **Learning Focus**: Authentication deferred to Phase 2+ (localhost-only in Phase 1)
- **Auto Documentation**: Swagger UI helps understand API structure

### API Structure

**12-15 Endpoints** across 4 routers:

```
/api/v1/
├── /health             (1 endpoint) Health check
├── /products           (5 endpoints) CRUD operations
│   ├── GET /           List products (paginated)
│   ├── POST /          Create product
│   ├── GET /{sku}      Get product by SKU
│   ├── PUT /{sku}      Update product
│   └── DELETE /{sku}   Delete product
├── /analysis           (3 endpoints) ML job management
│   ├── POST /detect    Submit image for analysis
│   ├── GET /{job_id}   Get job status
│   └── GET /{job_id}/detections  Get detection results
└── /detections         (2 endpoints) Query detections
    ├── GET /           List all detections (paginated)
    └── GET /           Filter by SKU or job_id
```

### Project Structure

```
src/shelf_monitor/api/
├── main.py                 # FastAPI app initialization
├── dependencies.py         # Shared dependencies (get_db, etc.)
└── routers/
    ├── __init__.py
    ├── health.py           # Health check
    ├── products.py         # Product CRUD
    ├── analysis.py         # Analysis jobs
    └── detections.py       # Detection queries
```

### FastAPI Application

**`main.py`** (app initialization):
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import health, products, analysis, detections
from ..database.session import engine
from ..database.models import Base

app = FastAPI(
    title="Retail Shelf Monitoring API",
    description="Backend API for shelf monitoring ML pipeline",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS (for future frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(detections.router, prefix="/api/v1")

# Create tables on startup (Phase 1 only; use Alembic in Phase 2+)
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
```

### Dependency Injection

**`dependencies.py`** (database session):
```python
from sqlalchemy.orm import Session
from ..database.session import SessionLocal

def get_db() -> Session:
    """
    Dependency to get database session.
    FastAPI will automatically close session after request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Usage in Router**:
```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..dependencies import get_db

router = APIRouter()

@router.post("/products")
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    """FastAPI injects database session automatically."""
    return crud.create_product(db, product)
```

### Pydantic Schemas

**`database/schemas.py`** (validation):
```python
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from decimal import Decimal

class ProductBase(BaseModel):
    sku: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    category_id: int = Field(..., gt=0)
    expected_price: Decimal = Field(..., gt=0, decimal_places=2)
    barcode: Optional[str] = Field(None, max_length=20)
    image_url: Optional[str] = None

class ProductCreate(ProductBase):
    """Schema for creating product (no id)."""
    pass

class ProductUpdate(BaseModel):
    """Schema for updating product (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    expected_price: Optional[Decimal] = Field(None, gt=0)
    barcode: Optional[str] = None
    image_url: Optional[str] = None

class ProductResponse(ProductBase):
    """Schema for product responses (includes id, timestamps)."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True  # Enable ORM mode (SQLAlchemy → Pydantic)

class AnalysisJobCreate(BaseModel):
    image_path: str
    challenge_type: str = Field(..., pattern='^(OOS_DETECTION|PRODUCT_RECOGNITION|STOCK_ESTIMATION|PRICE_VERIFICATION)$')

class AnalysisJobResponse(BaseModel):
    id: int
    image_path: str
    challenge_type: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    
    class Config:
        from_attributes = True
```

### Error Handling

**Custom Exception Handlers**:
```python
# main.py

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle validation errors with educational messages."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Validation Error",
            "detail": str(exc),
            "help": "Check request parameters and try again."
        }
    )

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "detail": "The requested resource does not exist.",
            "help": "Verify the SKU or ID and try again."
        }
    )
```

### Example Router

**`routers/products.py`**:
```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..dependencies import get_db
from ...database import crud, schemas

router = APIRouter(prefix="/products", tags=["products"])

@router.post("/", response_model=schemas.ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    """
    Create new product in catalog.
    
    Args:
        product: ProductCreate schema (sku, name, category_id, expected_price)
        
    Returns:
        ProductResponse with created product details
        
    Raises:
        400: If SKU already exists
        404: If category_id invalid
    """
    # Check if SKU exists
    existing = crud.get_product_by_sku(db, product.sku)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Product with SKU '{product.sku}' already exists."
        )
    
    return crud.create_product(db, product)

@router.get("/", response_model=List[schemas.ProductResponse])
def list_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all products with pagination."""
    return crud.get_products(db, skip=skip, limit=limit)

@router.get("/{sku}", response_model=schemas.ProductResponse)
def get_product(sku: str, db: Session = Depends(get_db)):
    """Get product by SKU."""
    product = crud.get_product_by_sku(db, sku)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{sku}' not found")
    return product
```

### Authentication (Deferred to Phase 2+)

**Phase 1**: No authentication (localhost:8000 only)

**Phase 2+ (Optional)**:
```python
# Simple API key authentication
from fastapi import Security
from fastapi.security.api_key import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

# Protect endpoints
@router.post("/products", dependencies=[Depends(verify_api_key)])
def create_product(...):
    pass
```

### API Documentation

**Auto-Generated Docs**:
- **Swagger UI**: `http://localhost:8000/docs` (interactive testing)
- **ReDoc**: `http://localhost:8000/redoc` (clean documentation)
- **OpenAPI JSON**: `http://localhost:8000/openapi.json` (schema export)

**Run Server**:
```bash
uvicorn src.shelf_monitor.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|----------------|
| **Flask** | Less modern; no auto API docs; more boilerplate |
| **Django REST Framework** | Overkill for learning; heavyweight; FastAPI simpler |
| **Single router file** | Poor organization; routers by domain clearer |
| **OAuth2 from start** | Overcomplicates Phase 1; defer to Phase 2+ |
| **GraphQL** | Adds complexity; REST simpler for learning |

---

## Summary & Next Steps

### Research Completion Status

| Task | Status | Output |
|------|--------|--------|
| **R1: Dataset Strategy** | ✅ Complete | SKU-110K subset (4K) + full (11K), COCO→YOLO conversion |
| **R2: Custom Vision** | ✅ Complete | 2 projects (OOS + recognition), 5 iterations each, quota monitoring |
| **R3: YOLO Configuration** | ✅ Complete | YOLOv8s, 50 epochs, batch 16, pretrained weights |
| **R4: Document Intelligence** | ✅ Complete | Read API, exponential backoff, regex price parsing, confidence >0.8 |
| **R5: Error Handling** | ✅ Complete | 3-retry backoff, educational messages, console logging |
| **R6: Testing Strategy** | ✅ Complete | Unit tests (core logic), integration tests (API + DB), >70% coverage |
| **R7: Database Design** | ✅ Complete | PostgreSQL, 5 tables (3NF), SQLAlchemy ORM, Alembic migrations |
| **R8: FastAPI Architecture** | ✅ Complete | Router structure, dependency injection, Pydantic validation |

### Key Decisions Summary

**Technology Stack**:
- **ML**: YOLOv8s (local), Azure Custom Vision (cloud comparison)
- **Database**: PostgreSQL 15+ with SQLAlchemy 2.0
- **Backend**: FastAPI 0.104+ with Pydantic validation
- **Migrations**: Alembic for schema versioning
- **Testing**: pytest + FastAPI TestClient + SQLite in-memory
- **Dataset**: SKU-110K (4K subset for Custom Vision, full for YOLO)

**Performance Targets**:
- Challenge 1: Precision >90%, Recall >85%
- Challenge 2: mAP@0.5 >85%, >10 FPS inference
- Challenge 3: Count accuracy >90%, MAPE <15%
- Challenge 4: OCR accuracy >95%, price extraction >90%

**Cost Estimate**: $0-20 total
- Azure free tiers (Custom Vision F0, Document Intelligence F0): $0
- PostgreSQL local: $0
- Azure ML (optional weeks 9-10): $5-20
- Total infrastructure cost: ~$0-20

### Phase 1 Ready

All technical decisions documented. Proceed to **Phase 1: Design & Contracts**:
1. Create `data-model.md` (5 database tables + 3 dataclasses)
2. Create `contracts/` directory (Python module interfaces + API contracts)
3. Create `quickstart.md` (installation + database setup + first API call)
4. Re-evaluate Constitution Check (verify no new violations)

**Next Command**: Implement Phase 1 design artifacts as defined in plan.md.

---

**Status**: ✅ Phase 0 Research Complete  
**Date**: December 10, 2025  
**Ready for**: Phase 1 Design & Contracts
