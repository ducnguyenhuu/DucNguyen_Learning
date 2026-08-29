# Retail Shelf Monitoring

> AI-powered retail shelf monitoring system using Azure AI & Computer Vision

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Azure](https://img.shields.io/badge/Azure-AI%20Services-0078D4.svg)](https://azure.microsoft.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Overview

This research project implements an intelligent retail shelf monitoring system that addresses the **top 4 critical challenges** in retail inventory management using computer vision and Azure AI services.

**Project Goals:**
- Learn Azure AI & Computer Vision through hands-on implementation
- Follow production-standard code organization
- Build working solutions for real retail problems

---

## 🎯 Top 4 Retail Shelf Challenges

> **Note**: This research project uses **public datasets only**. Challenges were selected based on data availability.

| # | Challenge | Business Impact | Solution Approach | Dataset |
|---|-----------|-----------------|-------------------|----------|
| **1** | **Out-of-Stock (OOS) Detection** | 4-8% revenue loss per year | Detect empty shelf spaces in real-time | SKU-110K |
| **2** | **Product Recognition** | Manual counting errors, labor costs | Automated SKU identification using object detection | SKU-110K, Grocery Store, RPC |
| **3** | **Stock Level Estimation** | Delayed restocking, lost sales | Visual product counting and quantity analysis | Derived from Challenge 2 |
| **4** | **Price Tag Verification** | Pricing errors, regulatory fines | OCR-based price extraction and validation | Azure Document Intelligence (pre-trained) |

---

## 🔬 Challenge Details

### Challenge 1: Out-of-Stock Detection

**Problem**: Empty shelves mean lost sales. Research shows retailers lose 4-8% of revenue annually due to out-of-stock situations.

**Technical Approach**:
- Detect shelf structure and regions
- Identify gaps/empty spaces between products
- Compare against expected planogram
- Generate real-time alerts for restocking

**Key Metrics**: Precision, Recall, Detection Latency

---

### Challenge 2: Product Recognition

**Problem**: Retail stores have thousands of SKUs with similar packaging. Manual identification is slow and error-prone.

**Technical Approach**:
- Train YOLOv8 for multi-product detection
- Fine-tune classifier for SKU-level identification  
- Handle varying orientations and partial occlusions
- Use Azure Custom Vision for rapid prototyping

**Key Metrics**: mAP@0.5, Classification Accuracy, Inference Speed (FPS)

---

### Challenge 3: Stock Level Estimation

**Problem**: Knowing what's on the shelf isn't enough - retailers need to know **how much** to plan restocking.

**Technical Approach**:
- Count detected products per SKU
- Estimate shelf depth (front-facing × estimated rows)
- Track depletion trends over time
- Predict restocking needs

**Key Metrics**: Count Accuracy, Mean Absolute Percentage Error (MAPE)

---

### Challenge 4: Price Tag Verification

**Problem**: Incorrect price tags cause customer complaints, checkout delays, and potential regulatory fines.

**Technical Approach**:
- Detect price tag regions near products
- Extract text using OCR (Azure AI Document Intelligence)
- Parse price values from various formats
- Compare against database prices

**Dataset Note**: Uses **Azure Document Intelligence pre-trained OCR** - no custom training required. The service handles text extraction from retail signage out-of-the-box.

**Key Metrics**: OCR Accuracy, Price Match Rate

---

## 🏗️ Project Structure (Production Standard)

```
retail-shelf-monitoring/
│
├── src/                              # Application source code
│   └── shelf_monitor/                # Main package
│       ├── __init__.py
│       │
│       ├── core/                     # Core business logic
│       │   ├── __init__.py
│       │   ├── detector.py           # Challenge 1 & 2: Detection
│       │   ├── classifier.py         # Challenge 2: Classification
│       │   ├── stock_analyzer.py     # Challenge 3: Stock levels
│       │   └── ocr.py                # Challenge 4: Price tags
│       │
│       ├── models/                   # ML model wrappers
│       │   ├── __init__.py
│       │   ├── base.py               # Base classes & data models
│       │   └── yolo.py               # YOLOv8 wrapper
│       │
│       ├── services/                 # External service integrations
│       │   ├── __init__.py
│       │   ├── azure_cv.py           # Azure Computer Vision
│       │   ├── azure_custom_vision.py
│       │   └── storage.py            # Azure Blob Storage
│       │
│       ├── api/                      # REST API (FastAPI)
│       │   ├── __init__.py
│       │   ├── app.py                # Application factory
│       │   ├── routes/               # API endpoints
│       │   │   ├── __init__.py
│       │   │   ├── detection.py
│       │   │   └── health.py
│       │   └── schemas/              # Request/Response models
│       │       ├── __init__.py
│       │       └── detection.py
│       │
│       ├── config/                   # Configuration
│       │   ├── __init__.py
│       │   └── settings.py           # Pydantic settings
│       │
│       └── utils/                    # Utilities
│           ├── __init__.py
│           ├── image.py              # Image processing helpers
│           └── logging.py            # Logging configuration
│
├── notebooks/                        # Research notebooks (by challenge)
│   ├── 01_out_of_stock_detection.ipynb
│   ├── 02_product_recognition.ipynb
│   ├── 03_stock_level_estimation.ipynb
│   └── 04_price_tag_verification.ipynb
│
├── data/                             # Data directory
│   ├── raw/                          # Original images
│   ├── processed/                    # Training datasets
│   │   ├── train/
│   │   ├── val/
│   │   └── test/
│   └── annotations/                  # Labels (COCO/YOLO format)
│
├── models/                           # Trained model artifacts
│   └── .gitkeep
│
├── tests/                            # Test suite
│   ├── __init__.py
│   ├── conftest.py                   # Pytest fixtures
│   ├── unit/                         # Unit tests
│   │   ├── __init__.py
│   │   └── test_detector.py
│   └── integration/                  # Integration tests
│       └── __init__.py
│
├── scripts/                          # Utility scripts
│   ├── train.py                      # Model training
│   ├── evaluate.py                   # Model evaluation
│   └── download_dataset.py           # Dataset download
│
├── docker/                           # Docker configuration
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── docs/                             # Documentation
│   ├── ARCHITECTURE.md               # System architecture
│   ├── API.md                        # API reference
│   └── DEPLOYMENT.md                 # Deployment guide
│
├── .github/                          # GitHub configuration
│   └── workflows/
│       └── ci.yml                    # CI/CD pipeline
│
├── pyproject.toml                    # Project metadata (PEP 517)
├── requirements.txt                  # Production dependencies
├── requirements-dev.txt              # Development dependencies
├── Makefile                          # Common commands
├── .env.example                      # Environment template
├── .gitignore
└── README.md
```

---

## 🛠️ Technology Stack

| Category | Technology | Purpose |
|----------|------------|---------|
| **ML Framework** | PyTorch + Ultralytics | YOLOv8 training & inference |
| **Azure AI** | Computer Vision, Custom Vision | Cloud-based AI services |
| **Azure ML** | Azure Machine Learning | MLOps & model management |
| **API** | FastAPI | REST API serving |
| **Storage** | Azure Blob Storage | Image & model storage |
| **Testing** | pytest | Unit & integration tests |
| **CI/CD** | GitHub Actions | Automated pipelines |
| **Container** | Docker | Containerization |

---

## 📊 Success Metrics

| Challenge | Model/Task | Target Metric |
|-----------|------------|---------------|
| 1. OOS Detection | Empty space detection | Precision > 90%, Recall > 85% |
| 2. Product Recognition | Object detection | mAP@0.5 > 85% |
| 3. Stock Estimation | Product counting | MAPE < 15% |
| 4. Price Verification | OCR + matching | Accuracy > 95% |

---

## 📚 Learning Path

| Week | Focus | Challenge | Deliverable |
|------|-------|-----------|-------------|
| 1-2 | Environment Setup | - | Dev environment, Azure resources |
| 3-4 | OOS + Detection | 1 & 2 | Detection model, empty space logic |
| 5-6 | Stock Estimation | 3 | Counting logic, trend analysis |
| 7-8 | Price Tags + API | 4 | OCR integration, REST API |
| 9-10 | MLOps + Deploy | - | Azure ML pipeline, deployment |

---

## 🚀 Quick Start

```bash
# Clone & setup
git clone <repo-url>
cd retail-shelf-monitoring
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure Azure credentials
cp .env.example .env
# Edit .env with your Azure keys

# Run tests
make test

# Start API
make run
```

---

## 📖 Documentation

- [Architecture Guide](ARCHITECTURE.md)


---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
