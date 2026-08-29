# Quickstart Guide - Retail Shelf Monitoring

**Last Updated**: December 26, 2025  
**Prerequisites**: Python 3.10+, Git, ~5GB disk space  
**Estimated Setup Time**: 15-20 minutes

---

## Overview

This guide walks you through setting up the Retail Shelf Monitoring API from scratch, verifying the installation, and running your first shelf analysis. You'll learn how to:

1. Install dependencies and configure the environment
2. Initialize the database with sample products
3. Start the FastAPI server and explore the API
4. Submit an image for analysis (Challenge 1: Gap Detection)
5. Retrieve analysis results and understand the output

---

## Table of Contents

- [1. Prerequisites Check](#1-prerequisites-check)
- [2. Project Setup](#2-project-setup)
- [3. Environment Configuration](#3-environment-configuration)
- [4. Database Initialization](#4-database-initialization)
- [5. Start the API Server](#5-start-the-api-server)
- [6. Verify Installation](#6-verify-installation)
- [7. Challenge 1 Walkthrough](#7-challenge-1-walkthrough-out-of-stock-detection)
- [8. Next Steps](#8-next-steps)
- [9. Troubleshooting](#9-troubleshooting)

---

## 1. Prerequisites Check

Before starting, verify you have the required tools:

```bash
# Check Python version (must be 3.10+)
python3 --version

# Check pip is available
pip3 --version

# Check Git is installed
git --version

# Verify disk space (need ~5GB for dataset + models)
df -h .
```

**Expected Output**:
```
Python 3.10.x or higher
pip 23.x.x or higher
git 2.x.x or higher
At least 5GB available
```

---

## 2. Project Setup

### Step 1: Clone the Repository

```bash
# Clone the project
git clone https://github.com/your-username/retail-shelf-monitoring.git
cd retail-shelf-monitoring
```

### Step 2: Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
# venv\Scripts\activate

# Verify activation (should show venv in prompt)
which python3
# Expected: /path/to/retail-shelf-monitoring/venv/bin/python3
```

### Step 3: Install Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install production dependencies
pip install -r requirements.txt

# Install development dependencies (optional - for testing)
pip install -r requirements-dev.txt

# Verify installation
pip list | grep fastapi
pip list | grep ultralytics
pip list | grep sqlalchemy
```

**Expected Output**:
```
fastapi        0.104.x
ultralytics    8.x.x
sqlalchemy     2.0.x
```

**Installation Time**: 5-7 minutes (depends on internet speed and PyTorch download)

---

## 3. Environment Configuration

### Step 1: Create .env File

```bash
# Copy example environment file
cp .env.example .env
```

### Step 2: Configure Essential Settings

Edit `.env` with your preferred text editor:

```bash
# Open in your editor
nano .env
# or
vim .env
# or
code .env  # VS Code
```

**Minimal Required Configuration** (for local development):

```dotenv
# Database (default is fine for local testing)
DATABASE_URL=sqlite:///data/retail_shelf_monitoring.db

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Application Settings
LOG_LEVEL=INFO
ENVIRONMENT=development

# ML Model Settings
CONFIDENCE_THRESHOLD=0.5
MIN_GAP_WIDTH=100
```

**Note**: Azure credentials are NOT required for Challenge 1 (Out-of-Stock Detection). We're using YOLOv8 trained on SKU-110K dataset, which runs 100% locally.

### Step 3: Verify Configuration

```bash
# Test settings loading
python3 -c "
from src.shelf_monitor.config.settings import settings
print('✅ Settings loaded successfully')
print(f'Database: {settings.database_url}')
print(f'API Port: {settings.api_port}')
print(f'Environment: {settings.environment}')
print(f'Log Level: {settings.log_level}')
"
```

**Expected Output**:
```
✅ Settings loaded successfully
Database: sqlite:///data/retail_shelf_monitoring.db
API Port: 8000
Environment: development
Log Level: INFO
```

---

## 4. Database Initialization

### Step 1: Create Data Directory

```bash
# Create data directory (if not exists)
mkdir -p data

# Verify directory structure
ls -la data/
```

### Step 2: Run Database Migrations

```bash
# Initialize database schema using Alembic
alembic upgrade head

# Verify tables were created
python3 -c "
from src.shelf_monitor.database.session import engine
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print('✅ Database tables created:')
for table in tables:
    print(f'  - {table}')
"
```

**Expected Output**:
```
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 001_initial, Initial schema

✅ Database tables created:
  - categories
  - products
  - analysis_jobs
  - detections
  - price_history
```

### Step 3: Seed Sample Products (Optional)

```bash
# Load 10 sample products into the database
python3 scripts/seed_products.py

# Verify products were inserted
python3 -c "
from src.shelf_monitor.database.session import SessionLocal
from src.shelf_monitor.database.models import Product
db = SessionLocal()
count = db.query(Product).count()
print(f'✅ {count} products in database')
db.close()
"
```

**Expected Output**:
```
✅ Seeded 10 products across 3 categories
✅ 10 products in database
```

---

## 5. Start the API Server

### Step 1: Start FastAPI Server

```bash
# Start the server (runs on http://localhost:8000)
uvicorn src.shelf_monitor.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected Output**:
```
INFO:     Will watch for changes in these directories: ['/path/to/retail-shelf-monitoring']
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using WatchFiles
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**What Just Happened?**
- FastAPI server started on port 8000
- Auto-reload enabled (changes to code will restart server)
- API documentation available at http://localhost:8000/docs
- Health check endpoints are live

### Step 2: Keep Server Running

**Important**: Keep this terminal open! The server must be running to handle API requests.

Open a **new terminal** for the next steps (and activate venv again):

```bash
# In new terminal
cd /path/to/retail-shelf-monitoring
source venv/bin/activate
```

---

## 6. Verify Installation

### Step 1: Test Root Endpoint

```bash
# Test API root endpoint
curl http://localhost:8000/

# Or use httpie (if installed)
http http://localhost:8000/
```

**Expected Response**:
```json
{
  "message": "Retail Shelf Monitoring API",
  "version": "1.0.0",
  "environment": "development",
  "docs": "/docs",
  "health": "/api/v1/health"
}
```

### Step 2: Check Health Status

```bash
# Basic health check
curl http://localhost:8000/api/v1/health

# Database connectivity check
curl http://localhost:8000/api/v1/health/db

# Kubernetes-style readiness probe
curl http://localhost:8000/api/v1/health/ready
```

**Expected Responses**:

**Basic Health** (`/api/v1/health`):
```json
{
  "status": "healthy",
  "service": "retail-shelf-monitoring-api",
  "version": "1.0.0",
  "timestamp": "2025-12-26T10:30:45.123456"
}
```

**Database Health** (`/api/v1/health/db`):
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2025-12-26T10:30:45.234567"
}
```

**Readiness Probe** (`/api/v1/health/ready`):
```json
{
  "status": "ready",
  "database": "connected",
  "models": "pending",
  "timestamp": "2025-12-26T10:30:45.345678"
}
```

**Note**: `models: "pending"` means YOLO models haven't been trained yet. This will change to `"loaded"` after completing Challenge 1 setup.

### Step 3: Explore API Documentation

Open your web browser and visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

**Interactive Features**:
- Try out endpoints directly from the browser
- See request/response schemas
- View parameter descriptions and examples
- Test authentication (when implemented)

---

## 7. Challenge 1 Walkthrough: Out-of-Stock Detection

### Overview

Challenge 1 addresses the **top retail problem**: detecting empty shelf spaces (gaps) that indicate out-of-stock products. This causes 4-8% revenue loss annually.

**Solution Approach**:
1. Use YOLOv8 trained on SKU-110K dataset (11,743 shelf images)
2. Detect all products in the shelf image
3. Analyze horizontal spacing between detections
4. Identify gaps wider than threshold (default: 100px)
5. Return gap locations for restocking alerts

### Prerequisites for Challenge 1

**Note**: The following steps assume you've already completed YOLO model training (Task T028 in Phase 2). If not, you'll need to:

```bash
# Download SKU-110K dataset (one-time setup)
python3 scripts/download_dataset.py

# Train YOLOv8 model (takes 2-3 hours on GPU)
python3 scripts/train_yolo.py --epochs 50 --batch 16

# Models will be saved to: models/yolo/oos-detection/
```

For this quickstart, we'll show the **expected workflow** once models are trained.

### Step 1: Prepare a Test Image

```bash
# Create test images directory
mkdir -p data/test_images

# Use a sample image from the test split
cp data/processed/SKU110K/images/test/test_0.jpg data/test_images/shelf_sample.jpg

# Verify image exists
ls -lh data/test_images/shelf_sample.jpg
```

### Step 2: Submit Image for Analysis (HTTP Endpoint)

Once the Challenge 1 endpoints are implemented (Task T034-T035), you can submit images:

```bash
# Submit shelf image for gap detection
curl -X POST http://localhost:8000/api/v1/analysis/submit \
  -F "file=@data/test_images/shelf_sample.jpg" \
  -F "analysis_type=gap_detection" \
  -F "min_gap_width=100"
```

**Expected Response**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "submitted",
  "analysis_type": "gap_detection",
  "submitted_at": "2025-12-26T10:35:00.123456",
  "estimated_completion": "2025-12-26T10:35:05.123456"
}
```

### Step 3: Check Analysis Status

```bash
# Poll for job status (replace {job_id} with actual ID)
curl http://localhost:8000/api/v1/analysis/550e8400-e29b-41d4-a716-446655440000
```

**Status Response (Processing)**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 50,
  "message": "Detecting products with YOLO..."
}
```

**Status Response (Complete)**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100,
  "analysis_type": "gap_detection",
  "submitted_at": "2025-12-26T10:35:00.123456",
  "completed_at": "2025-12-26T10:35:03.789012",
  "processing_time_ms": 3665,
  "results_url": "/api/v1/analysis/550e8400-e29b-41d4-a716-446655440000/results"
}
```

### Step 4: Retrieve Gap Detection Results

```bash
# Get detailed results
curl http://localhost:8000/api/v1/analysis/550e8400-e29b-41d4-a716-446655440000/results
```

**Expected Results**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "analysis_type": "gap_detection",
  "image_dimensions": {
    "width": 1920,
    "height": 1080
  },
  "detections": {
    "count": 47,
    "confidence_avg": 0.87,
    "products": [
      {
        "bbox": [120, 450, 180, 520],
        "confidence": 0.92,
        "class": "object"
      },
      {
        "bbox": [200, 445, 265, 525],
        "confidence": 0.89,
        "class": "object"
      }
      // ... 45 more detections
    ]
  },
  "gaps": {
    "count": 3,
    "total_width_px": 427,
    "regions": [
      {
        "x_start": 850,
        "x_end": 1025,
        "width": 175,
        "y_min": 440,
        "y_max": 680,
        "severity": "high",
        "message": "Large gap detected - possible out-of-stock"
      },
      {
        "x_start": 1450,
        "x_end": 1575,
        "width": 125,
        "severity": "medium",
        "message": "Medium gap detected - check stock levels"
      },
      {
        "x_start": 1800,
        "x_end": 1927,
        "width": 127,
        "severity": "medium",
        "message": "Medium gap detected - check stock levels"
      }
    ]
  },
  "metrics": {
    "stock_coverage_ratio": 0.78,
    "gap_to_product_ratio": 0.22,
    "detection_latency_ms": 342,
    "gap_analysis_latency_ms": 45
  },
  "recommendations": [
    "3 gap regions detected - immediate restocking recommended",
    "Gap at x=850 (175px wide) is largest - prioritize this area",
    "Overall shelf coverage is 78% - below target of 90%"
  ]
}
```

### Step 5: Understand the Results

**Key Metrics Explained**:

| Field | Description | Interpretation |
|-------|-------------|----------------|
| `detections.count` | Number of products detected | 47 products visible on shelf |
| `detections.confidence_avg` | Average YOLO confidence | 87% average confidence (high quality) |
| `gaps.count` | Number of empty spaces found | 3 gaps detected (potential stockouts) |
| `gaps.total_width_px` | Total width of all gaps | 427px of empty shelf space |
| `stock_coverage_ratio` | Shelf fullness percentage | 78% full (22% empty) |
| `gap.severity` | Gap importance level | high (>150px), medium (100-150px), low (<100px) |

**Business Actions**:
- **High severity gaps**: Immediate restocking needed (likely full product row missing)
- **Medium severity gaps**: Check stock levels (1-2 products missing)
- **Low severity gaps**: Monitor (might be intentional spacing or recent sale)

**Performance Benchmarks**:
- Detection latency: ~300-400ms on M1/M2 Mac or NVIDIA GPU
- Gap analysis: ~40-50ms (fast algorithm, no ML)
- Total end-to-end: <500ms (real-time capable)

### Step 6: Visualize Results (Jupyter Notebook)

For visual exploration, use the provided Jupyter notebook:

```bash
# Start Jupyter Lab
jupyter lab

# Open: notebooks/challenge_1_gap_detection.ipynb
```

The notebook will show:
- Original shelf image with bounding boxes
- Detected products highlighted in green
- Gap regions highlighted in red
- Confidence scores and gap widths annotated
- Side-by-side before/after comparison

**Notebook Features**:
- Interactive parameter tuning (confidence threshold, min gap width)
- Visual debugging (see what YOLO detected)
- Batch processing (analyze multiple images)
- Export results to CSV/JSON

---

## 8. Next Steps

Congratulations! 🎉 You've successfully set up the Retail Shelf Monitoring API and understand Challenge 1 workflow.

### Recommended Learning Path

**Week 1-2: Master Challenge 1**
1. Complete T025-T032: Implement detection and gap analysis logic
2. Train YOLO model on SKU-110K (T028-T030)
3. Build API endpoints (T033-T037)
4. Write unit tests (T038-T040)
5. Read guide: `docs/guides/challenge_1_oos_detection.md`

**Week 3-4: Challenge 2 - Object Counting**
1. Implement ObjectCounter class (T044-T047)
2. Build counting API (T048-T053)
3. Create visualization notebook (T054-T056)
4. Read guide: `docs/guides/challenge_2_object_counting.md`

**Week 5-6: Polish & Documentation**
1. Add error handling and input validation (T065-T067)
2. Write comprehensive tests (T069-T070)
3. Performance optimization (T071)
4. Final documentation (T072)

### Additional Resources

**Documentation**:
- [SPECIFICATION.md](../../SPECIFICATION.md) - Full project requirements
- [.specify/plans/plan.md](.specify/plans/plan.md) - Implementation plan
- [.specify/plans/tasks.md](.specify/plans/tasks.md) - Detailed task breakdown
- [.specify/plans/data-model.md](.specify/plans/data-model.md) - Database schema

**Guides** (will be created in Phase 4):
- `docs/guides/yolo_training.md` - YOLO training best practices
- `docs/guides/database_design.md` - SQLite schema deep dive
- `docs/guides/api_development.md` - FastAPI patterns

**External Learning**:
- [Ultralytics YOLOv8 Docs](https://docs.ultralytics.com/)
- [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/)
- [SQLAlchemy 2.0 Tutorial](https://docs.sqlalchemy.org/en/20/tutorial/)
- [SKU-110K Dataset Paper](https://arxiv.org/abs/1904.00853)

### Experiment Ideas

**For Learning**:
1. **Parameter Tuning**: Try different `confidence_threshold` values (0.3, 0.5, 0.7) - how does it affect detection count?
2. **Gap Width**: Change `min_gap_width` (50px, 100px, 200px) - what's the optimal threshold for your use case?
3. **Model Comparison**: Train YOLOv8n (nano) vs YOLOv8s (small) - speed vs accuracy tradeoff
4. **Dataset Exploration**: Analyze SKU-110K dataset distribution - are some shelf types better represented?

**For Fun**:
1. Take a photo of your own pantry/fridge - can the model detect products?
2. Create a "shelf fullness monitor" dashboard with matplotlib
3. Build a Discord/Slack bot that sends alerts when gaps are detected
4. Add a web frontend (React/Vue) for image upload and visualization

---

## 9. Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'src'"

**Cause**: Python can't find the `src` package  
**Solution**:
```bash
# Add project root to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or install package in editable mode
pip install -e .
```

### Issue: "No such file or directory: data/retail_shelf_monitoring.db"

**Cause**: Database migrations haven't been run  
**Solution**:
```bash
# Create data directory
mkdir -p data

# Run migrations
alembic upgrade head
```

### Issue: FastAPI server won't start (port already in use)

**Cause**: Another process is using port 8000  
**Solution**:
```bash
# Find process using port 8000
lsof -ti:8000

# Kill the process (replace PID)
kill -9 <PID>

# Or use a different port
uvicorn src.shelf_monitor.api.main:app --port 8001
```

### Issue: "torch not found" or "CUDA not available"

**Cause**: PyTorch not installed or GPU drivers missing  
**Solution**:
```bash
# For CPU-only (works on any machine)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# For NVIDIA GPU (CUDA 11.8)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# For macOS with M1/M2 (MPS acceleration)
# Already included in requirements.txt, no special install needed
```

### Issue: YOLO training is very slow

**Cause**: Running on CPU instead of GPU  
**Solution**:
```bash
# Check if GPU is available
python3 -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
python3 -c "import torch; print(f'MPS available: {torch.backends.mps.is_available()}')"

# If no GPU available:
# - Reduce batch size: --batch 8 (instead of 16)
# - Reduce epochs: --epochs 25 (instead of 50)
# - Use smaller model: yolov8n.pt (instead of yolov8s.pt)
# - Expected time on CPU: 6-8 hours (vs 2-3 hours on GPU)
```

### Issue: "alembic.util.exc.CommandError: Can't locate revision identified by 'head'"

**Cause**: Alembic migrations folder corrupted or not initialized  
**Solution**:
```bash
# Re-initialize Alembic (if needed)
alembic init alembic

# Or manually create migration
alembic revision -m "initial_schema"
alembic upgrade head
```

### Issue: Health check returns 503 (Service Unavailable)

**Cause**: Database connection failed  
**Solution**:
```bash
# Check database file exists
ls -lh data/retail_shelf_monitoring.db

# Test connection manually
python3 -c "
from src.shelf_monitor.database.session import SessionLocal
from sqlalchemy import text
db = SessionLocal()
db.execute(text('SELECT 1'))
print('✅ Database connection works')
db.close()
"

# Check .env DATABASE_URL is correct
grep DATABASE_URL .env
```

### Issue: CORS errors in browser when calling API

**Cause**: Frontend origin not in CORS_ORIGINS  
**Solution**:
```bash
# Edit .env and add your frontend URL
CORS_ORIGINS=http://localhost:3000,http://localhost:8080,http://localhost:5173

# Restart FastAPI server to reload settings
```

### Still Having Issues?

1. **Check logs**: `tail -f logs/app.log`
2. **Verify Python version**: `python3 --version` (must be 3.10+)
3. **Reinstall dependencies**: `pip install -r requirements.txt --force-reinstall`
4. **Check GitHub Issues**: Search for similar problems
5. **Ask for help**: Create a new issue with error details

---

## Summary Checklist

Before moving to Challenge 1 implementation, verify:

- [ ] Python 3.10+ installed and venv activated
- [ ] All dependencies installed (`pip list | grep fastapi`)
- [ ] .env file configured with DATABASE_URL, API_PORT, etc.
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] 10 sample products seeded (`python3 scripts/seed_products.py`)
- [ ] FastAPI server starts without errors
- [ ] Health endpoints return 200 OK
- [ ] API documentation accessible at http://localhost:8000/docs
- [ ] Logs being written to `logs/app.log`

**If all checkboxes are ticked**: ✅ You're ready to implement Challenge 1!

**If any checkbox is unchecked**: ⚠️ Review the relevant section above or check [Troubleshooting](#9-troubleshooting)

---

**Questions or feedback?** Open an issue on GitHub or refer to the [SPECIFICATION.md](../../SPECIFICATION.md) for detailed requirements.

**Happy coding! 🚀**
