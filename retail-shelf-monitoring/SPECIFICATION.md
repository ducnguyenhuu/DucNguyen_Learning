# Retail Shelf Monitoring - Project Specification

**Version**: 1.0.0  
**Date**: December 10, 2025  
**Project Type**: Research & Learning  
**Target Audience**: Junior Python Developers

---

## Executive Summary

This specification defines a **learning-focused** research project that implements retail shelf monitoring using Computer Vision and YOLO. The project addresses 2 critical retail challenges using SKU-110K public dataset, with emphasis on educational value and production-standard code organization.

**Key Constraints**:
- Research project, NOT production deployment
- Public dataset: SKU-110K (11,762 images, single "object" class)
- Simple implementations with professional code structure
- Educational documentation mandatory for all components
- Demonstration through Jupyter notebooks (NO UI/web development)
- Focus on code modules and notebook-based visualization
- Single-class object detection (no product-specific recognition)

---

## 1. Project Goals

### Primary Objectives

| Goal | Description | Success Criteria |
|------|-------------|------------------|
| **Master Computer Vision** | Understand CV fundamentals and object detection | Working YOLO model trained on SKU-110K dataset |
| **Production Code Practices** | Learn professional Python development | Code follows PEP 8, type hints, modular structure |
| **Solve Real Problems** | Address actual retail challenges | 2 challenges implemented with measurable metrics |
| **Full-Stack Integration** | Connect ML models to database and REST API | FastAPI backend serving YOLO predictions |

### Learning Outcomes

By completing this project, developers will understand:
- Object detection with YOLOv8 (single-class training)
- Gap detection algorithms (geometric analysis)
- Object counting from detection results
- Production Python package structure
- Computer vision evaluation metrics (mAP, precision, recall)
- **SQL and database design** (SQLite, normalization, indexing)
- **RESTful API development** (FastAPI, Pydantic validation)
- **Full-stack integration** (YOLO → Database → API)
- Jupyter notebooks for demonstration and visualization

### Prerequisites

**Required Knowledge** (Junior Python Developer baseline):

| Area | Requirement | Validation |
|------|-------------|------------|
| **Python** | 6-12 months experience with Python 3.x | Can write functions, classes, use standard library |
| **Python Basics** | Variables, loops, conditionals, functions | Comfortable reading/writing 50-line scripts |
| **OOP** | Basic classes, methods, inheritance | Can create simple class with `__init__` and methods |
| **Libraries** | Familiarity with pip, virtual environments | Has installed packages, created venv before |
| **Data Structures** | Lists, dicts, tuples | Can iterate, index, manipulate collections |
| **Files/Paths** | Basic file I/O | Can read/write text files |

**Helpful but NOT Required**:
- NumPy/Pandas (will be taught)
- Machine Learning concepts (project teaches from basics)
- Azure experience (starts from account creation)
- Computer Vision knowledge (explained step-by-step)
- Git proficiency (basic clone/commit sufficient)

**Technical Requirements**:
- Computer with Python 3.10+ installed
- 8GB+ RAM (16GB recommended for YOLO training)
- Internet connection for Azure services
- Text editor or IDE (VS Code recommended)
- Local GPU optional (NVIDIA with CUDA for faster YOLO training, but CPU works)

---

## 2. Challenge Specifications

### Challenge 1: Out-of-Stock Detection

**Business Context**: Retailers lose 4-8% annual revenue due to out-of-stock situations.

**Technical Specification**:
```yaml
Input: Shelf image (JPEG/PNG, min 640x480)
Output: List of empty shelf regions with bounding boxes
Method: Object detection → gap identification
Dataset: SKU-110K (11,762 images, 1.7M annotations)

Requirements:
  - Detect all products on shelf
  - Identify gaps between products as empty spaces
  - Flag gaps exceeding minimum width threshold
  - Return confidence scores for each detection

Metrics:
  - Precision: > 90%
  - Recall: > 85%
  - Detection latency: < 500ms per image
```

**Implementation Phases**:
1. **Phase 1**: Train Azure Custom Vision to detect products
2. **Phase 2**: Implement gap detection logic (simple threshold-based)
3. **Phase 3**: Refine with configurable parameters
4. **Phase 4**: Add validation and error handling

**Deliverables**:
- `core/detector.py`: Product detection class
- `notebooks/01_out_of_stock_detection.ipynb`: Experimentation notebook
- `docs/guides/challenge_1_oos_detection.md`: Implementation guide
- `tests/unit/test_detector.py`: Unit tests

---

### Challenge 2: Object Counting

**Business Context**: Retailers need quick inventory counts to manage restocking and track shelf occupancy.

**Technical Specification**:
```yaml
Input: Shelf image
Output: Total count of objects detected
Method: Object detection → counting
Dataset: SKU-110K (same single "object" class)

Requirements:
  - Use same YOLO model from Challenge 1
  - Count total objects detected
  - Track counts over time (optional trend analysis)
  - Report shelf occupancy rate
  - Simple Python implementation (no complex ML)

Metrics:
  - Count accuracy: > 95%
  - Processing time: < 100ms (after detection)
  - False positive rate: < 5%
```

**Implementation Phases**:
1. **Phase 1**: Reuse YOLO detections from Challenge 1
2. **Phase 2**: Implement counting logic (len(detections))
3. **Phase 3**: Add confidence filtering
4. **Phase 4**: Implement time-series tracking

**Deliverables**:
- `core/counter.py`: Object counting class
- `notebooks/02_object_counting.ipynb`: Demonstration notebook
- `docs/guides/challenge_2_object_counting.md`: Implementation guide
- `tests/unit/test_counter.py`: Unit tests



---

## 3. Technical Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│              FULL-STACK LEARNING ARCHITECTURE                │
└─────────────────────────────────────────────────────────────┘

Data Layer:
  - SQLite Database (analysis results, detection history)
  - SKU-110K Dataset (11,762 images, single "object" class)
  - Local filesystem (training images, models)

AI/ML Layer:
  - YOLOv8 (single-class object detection)
  - Python Analysis (gap detection, counting)

Backend Layer:
  - FastAPI REST API (analysis submission, results retrieval)
  - SQLAlchemy ORM (database operations)
  - Pydantic schemas (validation)
  - Alembic migrations (schema versioning)

Demonstration Layer:
  - Jupyter Notebooks (implementation + API interaction)
  - Python modules (production-structured code)
  - Markdown guides (educational documentation)
```

### Technology Stack

| Component | Technology | Justification |
|-----------|------------|---------------|
| **Language** | Python 3.10+ | Industry standard for ML/AI, rich ecosystem |
| **ML Framework** | PyTorch + Ultralytics | YOLOv8 standard, good documentation |
| **Database** | SQLite 3+ | Embedded SQL database, ACID compliance, zero-config |
| **Backend** | FastAPI 0.104+ | Modern Python web framework, auto-generated docs |
| **ORM** | SQLAlchemy 2.0+ | Python standard, type-safe database access |
| **Migrations** | Alembic | Database schema version control |
| **Testing** | pytest + httpx | Python standard, API testing support |
| **Notebooks** | Jupyter | Interactive demonstration and visualization |
| **Visualization** | matplotlib, seaborn | Standard plotting libraries |

---

## 4. Project Structure

### Directory Layout

```
retail-shelf-monitoring/
├── src/shelf_monitor/          # Main application package
│   ├── core/                   # ML business logic (2 challenges)
│   ├── models/                 # YOLO model wrapper
│   ├── database/               # Database layer (ORM, schemas, CRUD)
│   ├── api/                    # FastAPI backend (routers, dependencies)
│   ├── config/                 # Configuration management
│   └── utils/                  # Shared utilities
├── notebooks/                  # Jupyter notebooks (demonstration + API)
├── data/                       # Datasets (raw, processed, annotations)
├── models/                     # Trained YOLO model artifacts
├── tests/                      # Test suite (unit + integration)
│   ├── unit/                   # Unit tests (ML logic)
│   └── integration/            # Integration tests (API + DB)
├── scripts/                    # Utility scripts (setup, data prep)
├── alembic/                    # Database migrations
├── docs/                       # Documentation
│   ├── guides/                 # Implementation guides (mandatory)
│   ├── ARCHITECTURE.md         # System architecture
│   └── LEARNING_PATH.md        # Learning curriculum
└── .specify/                   # Project specifications
```

### Code Organization Standards

**Per Constitution Principle II**:
- One class per file
- Clear separation of concerns
- Type hints mandatory
- Docstrings (Google/NumPy style)
- Modular design (single responsibility)

**Example Module Structure**:
```python
# src/shelf_monitor/core/detector.py

from typing import List
from pathlib import Path

class ProductDetector:
    """
    Detects products in shelf images using Azure Custom Vision.
    
    This implements Challenge 1 (Out-of-Stock) and Challenge 2 
    (Product Recognition) by detecting product bounding boxes.
    
    Attributes:
        endpoint: Azure Custom Vision endpoint URL
        key: Azure Custom Vision API key
    """
    
    def __init__(self, endpoint: str, key: str) -> None:
        """Initialize detector with Azure credentials."""
        # Simple, clear implementation
        pass
    
    def detect(self, image_path: Path) -> List[Detection]:
        """
        Detect products in shelf image.
        
        Args:
            image_path: Path to input image
            
        Returns:
            List of Detection objects with bounding boxes and confidence
            
        Raises:
            ValueError: If image_path does not exist
            AzureError: If API call fails
        """
        # Implementation here
        pass
```

---

## 5. Data Requirements

### Public Datasets

| Dataset | Images | Annotations | Use Cases | Download |
|---------|--------|-------------|-----------|----------|
| **SKU-110K** | 11,762 | 1.7M bboxes | Challenge 1, 2, 3 | [GitHub](https://github.com/eg4000/SKU110K_CVPR19) |
| **Grocery Store** | 5,125 | 81 classes | Challenge 2 (alt) | [GitHub](https://github.com/marcusklasson/GroceryStoreDataset) |
| **RPC** | 83,739 | 200 SKUs | Challenge 2 (alt) | [Website](https://rpc-dataset.github.io/) |

### Data Preparation

```yaml
Directory Structure:
  data/raw/              # Original downloaded datasets
  data/processed/        # Preprocessed for training
    train/               # 70% split
    val/                 # 15% split
    test/                # 15% split
  data/annotations/      # COCO/YOLO format labels

Preprocessing Steps:
  1. Download dataset using scripts/download_dataset.py
  2. Convert annotations to YOLO format
  3. Split train/val/test
  4. Upload to Azure Blob Storage
  5. Register as Azure ML Dataset

Tools:
  - Python script: scripts/prepare_data.py
  - Format conversion: COCO → YOLO
  - Validation: Check for corrupt images
```

---

## 6. Development Workflow

### Phase-Based Development (Per Constitution Principle V)

**Phase 1: Get It Working**
- Minimal viable implementation
- Focus on core functionality
- Use simplest approach
- Manual testing acceptable

**Phase 2: Make It Clean**
- Add type hints
- Write docstrings
- Refactor for readability
- Add basic unit tests

**Phase 3: Make It Better**
- Optimize performance
- Handle edge cases
- Improve error messages
- Add integration tests

**Phase 4: Production-Ready**
- Comprehensive error handling
- Structured logging
- Input validation
- Complete test coverage

### Implementation Approach

**Sequential Challenge Execution** (Recommended):

1. Complete Challenge 1 Phase 1 → Test → Document
2. Complete Challenge 2 Phase 1 → Test → Document  
3. Complete Challenge 3 Phase 1 → Test → Document
4. Complete Challenge 4 Phase 1 → Test → Document
5. Iterate on phases 2-4 for selected challenges

**Rationale**: 
- Challenge 3 depends on Challenge 2 outputs (detection results)
- Sequential learning builds understanding incrementally
- Prevents context switching and incomplete implementations
- Allows early wins and motivation (complete notebook after each challenge)

**Parallel Work NOT Recommended**: Attempting multiple challenges simultaneously increases cognitive load and creates half-finished features (violates Constitution Principle V).

### Weekly Schedule

| Week | Focus | Challenges | Deliverables |
|------|-------|-----------|-------------|
| 1-2 | Environment + Database + Azure Setup | - | Azure resources, dev environment, SQLite, dataset downloaded |
| 3-4 | Database + API Foundation | - | Database schema, API endpoints, seed data |
| 5-6 | Detection Models | 1, 2 | Azure Custom Vision trained, OOS logic + notebook |
| 7-8 | Advanced Detection + Counting | 2, 3 | YOLOv8 trained, stock analyzer + notebooks |
| 9-10 | OCR + Demonstration | 4 | Document Intelligence integrated + notebook |
| 11-12 | MLOps + API Integration + Final Notebooks | All | Azure ML pipelines, complete API integration, demonstration notebooks |

---

## 7. Success Metrics

### Technical Metrics

| Challenge | Metric | Target | Measurement Method |
|-----------|--------|--------|-------------------|
| 1. OOS Detection | Precision | > 90% | TP / (TP + FP) on test set |
| 1. OOS Detection | Recall | > 85% | TP / (TP + FN) on test set |
| 2. Product Recognition | mAP@0.5 | > 85% | COCO evaluation on test set |
| 2. Product Recognition | Inference Speed | > 10 FPS | Average over 100 images |
| 3. Stock Estimation | MAPE | < 15% | Mean absolute % error |
| 4. Price Verification | OCR Accuracy | > 95% | Character-level accuracy |

### Learning Metrics

| Outcome | Assessment |
|---------|-----------|
| **Azure AI Understanding** | Can explain Custom Vision, Document Intelligence, Azure ML |
| **Computer Vision Skills** | Can train and evaluate YOLO models |
| **Python Proficiency** | Code follows PEP 8, uses type hints, proper structure |
| **MLOps Knowledge** | Can set up training pipelines, model registry |
| **Notebook Skills** | Can create clear, educational notebooks with visualizations |

---

## 8. Documentation Requirements (MANDATORY)

### Per Constitution Principle III

For **every** implemented feature, create markdown guide in `docs/guides/`:

**Template**:
```markdown
# [Feature Name] - Implementation Guide

## What
Brief description of what this implements.

## Why
Why this approach was chosen. What tradeoffs were made.

## How It Works
Step-by-step explanation of the implementation.

## Key Concepts
- Python concept 1 (e.g., type hints, context managers)
- Azure concept 1 (e.g., Custom Vision SDK)
- Design pattern used (if any)

## Usage Example
```python
# Working code example
```

## Common Issues
- Issue 1 and solution
- Issue 2 and solution

## Next Steps
What to learn next or how to extend this.
```

### Required Documentation Files

- [x] `README.md` - Project overview
- [x] `SPECIFICATION.md` - This document
- [ ] `docs/ARCHITECTURE.md` - System architecture (optional)
- [x] `docs/LEARNING_PATH.md` - Learning curriculum
- [ ] `docs/guides/challenge_1_oos_detection.md` - Challenge 1 guide
- [ ] `docs/guides/challenge_2_object_counting.md` - Challenge 2 guide
- [ ] `docs/guides/yolo_training.md` - YOLO training guide
- [ ] `docs/guides/database_design.md` - Database schema and SQL guide
- [ ] `docs/guides/api_development.md` - FastAPI development guide

---

## 9. Testing Strategy

### Testing Scope (Per Constitution)

**Unit Tests**: Core logic only
- Pure Python functions
- Business logic without external dependencies
- Focus: `core/`, `models/`, `utils/`

**Integration Tests**: Azure service interactions (optional)
- Test actual API calls with mock data
- Validate error handling
- Focus: `services/`

**Manual Testing**: Notebooks only
- Jupyter notebooks for experimentation and demonstration
- Visual inspection of outputs and visualizations

### Error Handling Requirements

**Phase 1 Minimum** (Must implement):

| Error Type | Handling Strategy | User Message |
|------------|------------------|-------------|
| **Invalid Image** | Validate format (JPEG/PNG), resolution (≥640x480) | "Invalid image: {filename}. Must be JPEG/PNG, min 640x480 resolution." |
| **Missing File** | Check path exists before processing | "File not found: {path}. Check file path and try again." |
| **Network Timeout** | Set 30s timeout, catch exception | "Request timed out after 30s. Check internet connection." |
| **Model Not Trained** | Check model exists before inference | "Model not found. Train model first using notebook section 2." |
| **YOLO Training Failure** | Save checkpoints every 10 epochs | "Training stopped at epoch X. Resuming from checkpoint." |

**Error Logging**:
- Log all errors to console with timestamp
- Educational error messages (explain what + why + how to fix)
- Phase 4: Add structured logging to file (`logs/app.log`)

**Recovery Strategies**:
- Training failures: Save checkpoints every 10 epochs (YOLO auto-checkpoint)
- Dataset download: Resume interrupted downloads (use `wget -c` or `requests` with Range headers)
- YOLO inference errors: Fallback to CPU if GPU fails

### Testing Standards

```python
# tests/unit/test_detector.py

import pytest
from shelf_monitor.core.detector import ProductDetector

def test_detector_initialization():
    """Test detector can be initialized with credentials."""
    detector = ProductDetector(endpoint="test", key="test")
    assert detector.endpoint == "test"

def test_detect_invalid_image_path():
    """Test detector raises error for non-existent image."""
    detector = ProductDetector(endpoint="test", key="test")
    with pytest.raises(ValueError):
        detector.detect(Path("nonexistent.jpg"))
```

**Coverage Target**: > 70% for core modules (not strict requirement)

---

## 10. Database Design

### Schema Overview

**3 SQLite Tables** (3NF normalized):

| Table | Purpose | Key Fields |
|-------|---------|------------|
| **analysis_jobs** | Tracks ML analysis runs | id, image_path, challenge_type, status, created_at |
| **detections** | Individual object detections | id, analysis_job_id, bbox (x/y/w/h), confidence |
| **categories** | Product categories (optional) | id, name, description |
| **products** | Product catalog (optional) | id, sku, name, category_id |

### Entity Relationships

```
analysis_jobs (1) ----< (many) detections

Optional (if using product catalog):
categories (1) ----< (many) products
```

### Sample SQL Queries

**Get all products in a category**:
```sql
SELECT p.sku, p.name, p.expected_price
FROM products p
JOIN categories c ON p.category_id = c.id
WHERE c.name = 'Beverages';
```

**Get detections for analysis job**:
```sql
SELECT d.sku, d.confidence, d.bbox_x, d.bbox_y
FROM detections d
WHERE d.analysis_job_id = 123
ORDER BY d.confidence DESC;
```

**Count products per SKU from analysis**:
```sql
SELECT d.sku, COUNT(*) as count
FROM detections d
WHERE d.analysis_job_id = 123
GROUP BY d.sku;
```

**Price history for SKU**:
```sql
SELECT detected_price, detected_at
FROM price_history
WHERE sku = 'coca_cola_500ml'
ORDER BY detected_at DESC
LIMIT 10;
```

### Migration Strategy

**Alembic workflow**:
```bash
# Create new migration
alembic revision --autogenerate -m "Add products table"

# Review generated migration in alembic/versions/

# Apply migration
alembic upgrade head

# Rollback if needed
alembic downgrade -1
```

---

## 11. API Specification

### RESTful Endpoints

**Base URL**: `http://localhost:8000/api/v1`

**Core Endpoints** (9 implemented in Phase 1):

| Endpoint | Method | Purpose | Request Body | Response |
|----------|--------|---------|--------------|----------|
| `/health` | GET | Health check | - | `{"status": "healthy"}` |
| `/products` | GET | List products | - | `[{sku, name, ...}]` |
| `/products` | POST | Create product | `{sku, name, ...}` | `{id, sku, ...}` |
| `/products/{sku}` | GET | Get product | - | `{sku, name, ...}` |
| `/products/{sku}` | PUT | Update product | `{name, price, ...}` | `{sku, name, ...}` |
| `/products/{sku}` | DELETE | Delete product | - | `204 No Content` |
| `/analysis/detect` | POST | Submit analysis | `image: file` | `{job_id, status}` |
| `/analysis/{job_id}` | GET | Get job status | - | `{job_id, status, ...}` |
| `/analysis/{job_id}/detections` | GET | Get detections | - | `[{sku, bbox, ...}]` |

**Optional Endpoints** (Phase 4 extensions):
- `/detections` GET - Query all detections with filters
- `/categories` GET/POST - Category management
- `/price-history/{sku}` GET - Price tracking over time
- `/statistics/stock` GET - Stock analysis aggregates

### API Usage Examples

**Create product**:
```bash
curl -X POST http://localhost:8000/api/v1/products \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "coca_cola_500ml",
    "name": "Coca Cola 500ml",
    "category_id": 1,
    "expected_price": 2.99
  }'
```

**Submit analysis job**:
```bash
curl -X POST http://localhost:8000/api/v1/analysis/detect \
  -F "image=@shelf_001.jpg" \
  -F "challenge_type=PRODUCT_RECOGNITION"
```

**Get analysis results**:
```bash
curl http://localhost:8000/api/v1/analysis/123/detections
```

### Interactive API Documentation

FastAPI auto-generates interactive documentation:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

---

## 13. Risk & Mitigation

### Required Azure Resources

| Service | SKU | Purpose | Estimated Cost |
|---------|-----|---------|---------------|
| **Custom Vision** | F0 (Free) | Product detection training | $0 |
| **Document Intelligence** | F0 (Free) | Price tag OCR | $0 |
| **Blob Storage** | Standard LRS | Dataset and model storage | ~$0.20/month |
| **Azure ML** | Pay-as-you-go | Training compute, MLOps | ~$5-20/month* |

*Use spot instances and auto-shutdown to minimize costs.

### Azure Free Tier Quota Limits

**Critical Constraints** (F0 tier):

| Service | Limit | Impact on Project |
|---------|-------|-------------------|
| **Custom Vision** | 2 projects max | Use 1 for Challenge 1 (OOS), 1 for Challenge 2 (Product Recognition) |
| **Custom Vision** | 5,000 training images | Use subset of SKU-110K dataset (~4,000 images) |
| **Custom Vision** | 10,000 predictions/month | Sufficient for testing and evaluation |
| **Custom Vision** | 10 training iterations | Limited experimentation - plan iterations carefully |
| **Document Intelligence** | 500 pages/month | Adequate for Challenge 4 testing (~100-200 test images) |
| **Document Intelligence** | 15 requests/minute | Rate limiting - implement retry logic with exponential backoff |

**Quota Exceeded Handling**:
- Monitor usage via Azure Portal
- Implement request counting in code
- Set up Azure budget alerts (recommended: $5 threshold)
- Fallback: Use local YOLO inference if Custom Vision exhausted

### Setup Steps

1. Create Azure subscription (free tier)
2. Create resource group: `rg-retail-shelf-monitoring`
3. Create Custom Vision resource (Training + Prediction)
4. Create Document Intelligence resource
5. Create Storage Account
6. Create Azure ML Workspace
7. Configure `.env` with credentials

**Setup Guide**: See `docs/guides/azure_setup.md` (to be created)

---

## 11. Implementation Checklist

### Environment Setup
- [ ] Python 3.10+ installed
- [ ] Python 3.10+ with SQLite support (built-in)
- [ ] Virtual environment created
- [ ] Dependencies installed (`requirements.txt`)
- [ ] Database created and migrated (Alembic)
- [ ] Azure subscription created
- [ ] Azure resources provisioned
- [ ] `.env` file configured (Azure + database connection)

### Challenge 1: Out-of-Stock Detection
- [ ] Azure Custom Vision project created
- [ ] SKU-110K dataset downloaded
- [ ] Training images uploaded to Custom Vision
- [ ] Model trained and evaluated
- [ ] Gap detection logic implemented
- [ ] Unit tests written
- [ ] Implementation guide documented
- [ ] Notebook completed

### Challenge 2: Product Recognition
- [ ] Azure Custom Vision classification project
- [ ] YOLOv8 training environment set up
- [ ] Model trained on SKU-110K
- [ ] Inference optimized
- [ ] Unit tests written
- [ ] Implementation guide documented
- [ ] Notebook completed

### Challenge 3: Stock Level Estimation
- [ ] Stock counting logic implemented
- [ ] Depth estimation heuristics added
- [ ] Unit tests written
- [ ] Implementation guide documented
- [ ] Notebook completed

### Challenge 4: Price Tag Verification
- [ ] Document Intelligence integrated
- [ ] Price parsing logic implemented
- [ ] Unit tests written
- [ ] Implementation guide documented
- [ ] Notebook completed

### Backend Development
- [ ] Database schema designed (5 tables: products, categories, analysis_jobs, detections, price_history)
- [ ] Alembic migrations created
- [ ] SQLAlchemy ORM models implemented
- [ ] Pydantic schemas defined
- [ ] CRUD operations implemented
- [ ] FastAPI application structured
- [ ] API routers implemented (products, analysis, detections, health)
- [ ] API endpoint tests written
- [ ] Database seeded with product catalog

### Demonstration Notebooks
- [ ] All 4 challenge notebooks completed
- [ ] API integration demonstrated in notebooks
- [ ] Code execution verified
- [ ] Outputs and visualizations included
- [ ] Educational explanations added
- [ ] Results documented

### MLOps & Deployment
- [ ] Azure ML pipelines configured
- [ ] Models registered in model registry
- [ ] Inference endpoint deployed (optional)
- [ ] Monitoring configured (optional)

---

## 14. Constraints & Boundaries

### In Scope (Per Constitution)
✅ 4 ML challenges with public datasets
✅ Azure AI services (Custom Vision, Document Intelligence, Azure ML)
✅ **SQLite database** (product catalog, analysis results)
✅ **FastAPI REST API** (CRUD operations, analysis submission)
✅ **Database design** (schema, migrations, SQL queries)
✅ Local development with Jupyter notebooks
✅ Python modules with production-standard structure
✅ Notebook-based demonstration and API interaction
✅ Basic MLOps with Azure ML
✅ Educational documentation for all components

### Out of Scope
❌ UI development (web/mobile interfaces)
❌ Real-time camera feeds
❌ IoT Hub / Edge deployment
❌ Multi-region deployment
❌ Kubernetes orchestration
❌ Microservices architecture
❌ Advanced monitoring (Application Insights)
❌ Enterprise authentication (Azure AD B2C)
❌ Production-scale performance optimization

---

## 15. Acceptance Criteria

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Azure costs exceed budget** | High | Use free tiers, set budget alerts, auto-shutdown compute |
| **Dataset quality issues** | Medium | Use well-established public datasets (SKU-110K) |
| **Model performance below target** | Medium | Start with Azure Custom Vision, iterate with YOLO |
| **Complexity creep** | High | Constitution enforcement, regular reviews |
| **Time overrun** | Medium | Fixed 12-week timeline (added 2 weeks for backend), prioritize Phase 1 completions |
| **Database complexity** | Medium | Start with simple schema, use ORM, follow normalization best practices |

---

## 15. Acceptance Criteria

### Project Completion Definition

The project is considered complete when:

1. **All 4 ML challenges implemented** with working code
2. **Backend infrastructure complete**:
   - Database schema migrated and seeded
   - REST API endpoints functional
   - API tests passing
3. **Technical metrics met** (or documented why not)
4. **Documentation complete**:
   - All implementation guides written (ML + database + API)
   - Code has docstrings and comments
   - README accurate and up-to-date
5. **Code quality verified**:
   - Follows PEP 8
   - Type hints present
   - Production structure maintained
6. **Notebooks complete**: All 4 challenge notebooks:
   - Execute successfully end-to-end
   - Display clear outputs and visualizations
   - Include educational explanations
   - Demonstrate API interactions
7. **Tests passing**: Unit tests for core modules + integration tests for API

### Quality Gates

**Before merging code**:
- [ ] Code review checklist passed (5 questions from constitution)
- [ ] Implementation guide created
- [ ] Unit tests written (if applicable)
- [ ] Code runs successfully

**Before project completion**:
- [ ] All acceptance criteria met
- [ ] Peer review completed (if available)
- [ ] Final documentation review

---

## 16. Future Enhancements (Post-Learning)

Once learning objectives are met, consider:

- **Web UI**: React/Vue dashboard for visualization
- **Real-time inference**: Deploy to Azure Container Instances
- **Model monitoring**: Track performance drift
- **Advanced features**: A/B testing, canary deployments
- **Production deployment**: IoT Hub, Edge devices
- **Mobile app**: Flutter application
- **Authentication**: JWT tokens, OAuth2 flow
- **Background jobs**: Celery for async ML processing

**Important**: These are explicitly out of scope for the learning phase.

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **API** | Application Programming Interface - contract for software communication |
| **CRUD** | Create, Read, Update, Delete - basic database operations |
| **ORM** | Object-Relational Mapping - database abstraction layer |
| **3NF** | Third Normal Form - database normalization level |
| **mAP** | Mean Average Precision - object detection metric |
| **MAPE** | Mean Absolute Percentage Error - regression metric |
| **SKU** | Stock Keeping Unit - unique product identifier |
| **OOS** | Out-of-Stock - empty shelf condition |
| **OCR** | Optical Character Recognition - text extraction from images |
| **MLOps** | Machine Learning Operations - ML lifecycle management |
| **YOLO** | You Only Look Once - real-time object detection architecture |

---

## Appendix B: Reference Architecture

See `docs/ARCHITECTURE.md` for detailed technical architecture.

---

## Appendix C: Learning Resources

- [Azure AI Documentation](https://docs.microsoft.com/azure/cognitive-services/)
- [YOLOv8 Documentation](https://docs.ultralytics.com/)
- [SKU-110K Paper](https://arxiv.org/abs/1904.00853)
- [PyTorch Tutorials](https://pytorch.org/tutorials/)
- [Jupyter Notebook Documentation](https://jupyter-notebook.readthedocs.io/)

---

**Document Control**

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2025-12-10 | System | Initial specification created from README.md |

---

**Approval**

This specification aligns with the Project Constitution and defines a complete, achievable learning project scope.

**Constitution Compliance**: ✅ All principles followed
- Learning-first approach maintained
- Production structure with simple implementation
- Educational documentation mandatory
- Code quality for learning ensured
- Incremental complexity enforced
