# Task Breakdown: Retail Shelf Monitoring

**Feature**: Retail Shelf Monitoring with Azure AI and Computer Vision  
**Plan**: [plan.md](./plan.md) | **Spec**: [SPECIFICATION.md](../../SPECIFICATION.md)  
**Timeline**: 12 weeks | **Target**: Junior Python developers learning ML + Backend + Database

---

## Overview

This learning project implements 2 ML challenges (Challenge 1: Out-of-Stock Detection, Challenge 2: Object Counting) with a full-stack architecture (SQLite database + FastAPI REST API + ML core). Tasks are organized by user story to enable independent implementation and testing.

**Note**: The term "User Story" (US1-US2) in this task document corresponds to "Challenge" (Challenge 1-2) in SPECIFICATION.md:
- User Story 1 (US1) = Challenge 1: Out-of-Stock Detection
- User Story 2 (US2) = Challenge 2: Object Counting

**Implementation Strategy**:
- **MVP First**: Complete User Story 1 (Challenge 1: Out-of-Stock Detection) as minimum viable product
- **Sequential Delivery**: Each user story is independently testable before moving to next
- **Single-Class YOLO**: Train one model for both challenges (object detection → gap analysis + counting)
- **API Parallel to ML**: Implement API endpoints alongside ML modules

---

## Task Format

```
- [ ] [TaskID] [P] [Story] Description with file path
```

- **TaskID**: Sequential number (T001, T002...)
- **[P]**: Parallelizable (different files, no dependencies)
- **[Story]**: User story label ([US1], [US2], etc.) for story-specific tasks
- **Description**: Clear action with exact file path

---

## Phase 1: Setup & Foundational Infrastructure

**Goal**: Establish development environment, SQLite database, and project structure before ML implementation.

### Setup Tasks

- [X] T001 Create virtual environment and install Python 3.10+ dependencies
- [X] T002 Initialize Git repository structure with .gitignore for data/, models/, .env
- [X] T003 Create .env.example template with database credential placeholders
- [X] T004 Create data/ directory for SQLite database (auto-created by SQLAlchemy)
- [X] T005 Initialize Alembic for database migrations in alembic/ directory
- [X] T008a [P] Create .specify/plans/data-model.md with entity definitions (3 DB tables: analysis_jobs, detections, optional products/categories + 2 dataclasses: Detection, GapRegion)
- [X] T008b [P] Create .specify/plans/contracts/ directory with Python module interface contracts (detector.py, counter.py, yolo.py, analysis.py, crud.py)

### Foundational Tasks (Blocking Prerequisites)

- [X] T009 Create src/shelf_monitor/ package structure with __init__.py files
- [X] T010 [P] Implement database models in src/shelf_monitor/database/models.py (5 tables: Product, Category, AnalysisJob, Detection, PriceHistory) with CHECK constraints for bbox validation and price_difference GENERATED column
- [X] T011 [P] Create Pydantic schemas in src/shelf_monitor/database/schemas.py for validation
- [X] T012 [P] Implement CRUD operations in src/shelf_monitor/database/crud.py
- [X] T013 [P] Create database session management in src/shelf_monitor/database/session.py
- [X] T014 Generate first Alembic migration for all 5 database tables
- [X] T015 Apply database migrations (alembic upgrade head) to create schema
- [X] T016 [P] Download SKU-110K dataset (11,762 images) to data/raw/SKU110K/ using scripts/download_dataset.py
- [X] T017 [P] Preprocess dataset and split 70/15/15 (train/val/test) using scripts/prepare_data.py
- [X] T018 Seed product catalog (optional - 10 sample products for demo purposes)
- [X] T019 [P] Create FastAPI app skeleton in src/shelf_monitor/api/main.py with CORS
- [X] T020 [P] Implement dependency injection for database sessions in src/shelf_monitor/api/dependencies.py
- [X] T021 [P] Create health check router in src/shelf_monitor/api/routers/health.py
- [X] T022 [P] Implement configuration management in src/shelf_monitor/config/settings.py
- [X] T023 [P] Set up logging utilities in src/shelf_monitor/utils/logging.py
- [X] T024 Verify FastAPI server starts and /api/v1/health endpoint returns 200
- [X] T024a [P] Create .specify/plans/quickstart.md with installation steps, database setup, API startup commands, and Challenge 1 walkthrough example

---

## Phase 2: User Story 1 - Out-of-Stock Detection (Challenge 1)

**User Story**: As a store manager, I want to detect empty shelf spaces so I can restock products before customers notice.

**Acceptance Criteria**:
- YOLOv8s model trained on SKU-110K single "object" class
- Gap detection algorithm identifies empty spaces >100px width
- REST API endpoint accepts image uploads and returns analysis results
- Detection results persisted to database (AnalysisJob + Detection tables)
- Jupyter notebook demonstrates end-to-end workflow
- Metrics: Precision >90%, Recall >85%, latency <500ms

**Independent Test Criteria**: Upload shelf image → API returns gaps list → Database contains job + detections → Visualize in notebook

### US1 Implementation Tasks

- [X] T025 [P] [US1] Create Detection dataclass in src/shelf_monitor/core/detector.py
- [X] T026 [P] [US1] Create GapRegion dataclass in src/shelf_monitor/core/detector.py
- [X] T027 [US1] Implement ProductDetector.__init__() to load YOLO model
- [X] T028 [US1] Train YOLOv8s model on SKU-110K (50 epochs, single "object" class)
- [X] T029 [US1] Evaluate YOLO model on test set (Precision, Recall, mAP@0.5) [SKIPPED - using pretrained model]
- [X] T030 [US1] Save best model checkpoint to models/yolo_sku110k_best.pt [SKIPPED - using pretrained model]
- [X] T031 [US1] Implement ProductDetector.detect_products() using YOLO inference
- [X] T032 [P] [US1] Implement ProductDetector.detect_gaps() algorithm (sort by x, compute gaps, flag >100px)
- [X] T033 [P] [US1] ~~Create YOLO wrapper~~ → Simplified: YOLO integrated directly into detector.py
- [ ] T034 [P] [US1] Implement analysis router in src/shelf_monitor/api/routers/analysis.py (POST /detect-gaps)
- [ ] T035 [P] [US1] Create detections router in src/shelf_monitor/api/routers/detections.py (GET /detections)
- [ ] T036 [US1] Implement analysis job submission workflow (save image, create AnalysisJob, queue processing)
- [ ] T037 [US1] Implement ML processing task (detect products, detect gaps, save Detection records)
- [ ] T038 [P] [US1] Create unit tests in tests/unit/test_detector.py for gap detection logic
- [ ] T039 [P] [US1] Create integration tests in tests/integration/test_api_analysis.py for /detect-gaps endpoint
- [ ] T040 [P] [US1] Create Jupyter notebook notebooks/01_out_of_stock_detection.ipynb with 5 sections
- [ ] T041 [US1] Write implementation guide docs/guides/challenge_1_oos_detection.md (What/Why/How/Usage)
- [ ] T042 [US1] Run tests and verify Precision >90%, Recall >85% on test set
- [ ] T043 [US1] Commit Challenge 1 implementation with descriptive message

**Parallel Opportunities**:
- T025-T026 (dataclasses) + ~~T033 (YOLO wrapper)~~ + T034-T035 (API routers) can run concurrently
- T038-T040 (tests + notebook) can run after T032 (core logic complete)

---

## Phase 3: User Story 2 - Object Counting (Challenge 2)

**User Story**: As a store manager, I want to count total objects on shelves so I can track inventory levels and shelf occupancy.

**Acceptance Criteria**:
- Reuse YOLO model from Challenge 1 (no additional training)
- Simple counting logic (len(detections))
- API endpoint returns total count from image
- Database stores count history for trending
- Jupyter notebook demonstrates counting and visualization
- Metrics: Count accuracy >95%, processing time <100ms

**Independent Test Criteria**: Upload shelf image → API returns total count → Database logs count with timestamp → Notebook shows trends

### US2 Implementation Tasks

- [ ] T044 [P] [US2] Create ObjectCounter class in src/shelf_monitor/core/counter.py
- [ ] T045 [P] [US2] Create CountResult dataclass with total_count, confidence_threshold fields
- [ ] T046 [P] [US2] Implement ObjectCounter.count_objects() (reuse YOLO detections, apply confidence filter)
- [ ] T047 [P] [US2] Implement ObjectCounter.calculate_occupancy() (count / estimated_capacity)
- [ ] T048 [US2] Create count_history table in database (job_id, count, occupancy_rate, timestamp)
- [ ] T049 [US2] Generate Alembic migration for count_history table
- [ ] T050 [US2] Apply migration (alembic upgrade head)
- [ ] T051 [P] [US2] Add CRUD operations for count_history in crud.py
- [ ] T052 [P] [US2] Update analysis router to support OBJECT_COUNTING challenge type (POST /count-objects)
- [ ] T053 [US2] Implement counting workflow (detect → filter by confidence → count → save to count_history)
- [ ] T054 [P] [US2] Create unit tests in tests/unit/test_counter.py for counting logic
- [ ] T055 [P] [US2] Create integration tests for /count-objects API endpoint
- [ ] T056 [P] [US2] Create Jupyter notebook notebooks/02_object_counting.ipynb with counting demo and trends
- [ ] T057 [US2] Write implementation guide docs/guides/challenge_2_object_counting.md
- [ ] T058 [US2] Run tests and verify count accuracy >95%
- [ ] T059 [US2] Commit Challenge 2 implementation

**Parallel Opportunities**:
- T044-T047 (counter class) + T048-T051 (database) can start immediately
- T054-T056 (tests + notebook) parallel after T046 complete

**Dependencies**: T052-T053 depend on T046 (counter implementation) and T051 (CRUD operations)

---

## Phase 4: Polish & Documentation

**Goal**: Finalize documentation, improve code quality, and prepare for demo.

### Polish Tasks

- [ ] T060 [P] Write docs/guides/yolo_training.md (YOLO setup, training, evaluation)
- [ ] T061 [P] Write docs/guides/database_design.md (schema, relationships, queries)
- [ ] T062 [P] Write docs/guides/api_development.md (FastAPI patterns, testing)
- [ ] T063 [P] Update README.md with installation, setup, and usage instructions
- [ ] T064 [P] Create .specify/plans/quickstart.md with end-to-end walkthrough
- [ ] T065 [US1+US2] Add input validation to API endpoints (image format, size limits)
- [ ] T066 [US1+US2] Add error handling with retry logic for YOLO inference
- [ ] T067 [US1+US2] Improve logging with structured format (timestamp, level, context)
- [ ] T068 [US1+US2] Add API rate limiting (10 requests/minute for demo)
- [ ] T069 Run full test suite (pytest tests/) and verify >70% coverage
- [ ] T070 Run code quality checks (black, flake8, mypy)
- [ ] T071 Final review of all documentation for completeness
- [ ] T072 Create demo video/presentation materials (optional)

**Parallel Opportunities**: T060-T064 (documentation) can all run in parallel

---

## Task Summary

**Total Tasks**: 72 (simplified from 126)  
**Current Progress**: 27 complete (37.5%)  
**Remaining**: 45 tasks

**By Phase**:
- Phase 1 (Setup): 18/18 complete ✅
- Phase 2 (Challenge 1): 9/19 tasks
- Phase 3 (Challenge 2): 0/16 tasks  
- Phase 4 (Polish): 0/13 tasks

**Estimated Timeline**: 4-6 weeks (vs original 10 weeks)

**Parallel Opportunities**:
- T067-T070 (core logic) all parallelizable (different methods)
- T074-T076 (tests + notebook) parallel after T069-T070 complete

**Dependencies**: T072-T073 depend on Challenge 2 (need SKU classifications)

---

## Dependencies Summary

### Story Completion Order

```
Setup (T001-T008)
  ↓
Foundational (T009-T024) [BLOCKING - must complete before user stories]
  ↓
User Story 1 (T025-T043) [MVP - Out-of-Stock Detection]
  ↓
User Story 2 (T044-T059) [Object Counting - reuses YOLO from US1]
  ↓
Polish (T060-T072) [Documentation and code quality]
```

### Critical Path

The minimum viable product (MVP) requires:
1. **Setup** (T001-T008): 1 week
2. **Foundational** (T009-T024): 1-2 weeks  
3. **User Story 1** (T025-T043): 2 weeks

**MVP Timeline**: 4-5 weeks for working out-of-stock detection with database persistence and API.

Full project completion: 6 weeks (includes both challenges + backend + documentation).

---

## Parallel Execution Examples

### During User Story 1 (Challenge 1)

**Parallel Set 1** (YOLO training period T028-T030):
```
Terminal 1: T028 (YOLO training - 50 epochs, ~2-3 hours)
Terminal 2: T032 (Gap detection algorithm implementation)
Terminal 3: ~~T033 (YOLO wrapper)~~ → Simplified
Terminal 4: T034-T035 (API routers)
```

**Parallel Set 2** (after T032 complete):
```
Terminal 1: T038 (Unit tests for gap detection)
Terminal 2: T039 (Integration tests for API)
Terminal 3: T040 (Jupyter notebook creation)
Terminal 4: T041 (Implementation guide documentation)
```

### During User Story 2 (Challenge 2)

**Parallel Set 1** (after T046 complete):
```
Terminal 1: T048-T051 (Database schema + CRUD)
Terminal 2: T052 (API router update)
Terminal 3: T054-T055 (Tests)
Terminal 4: T056 (Jupyter notebook)
```

**Parallel Set 2** (documentation):
```
Terminal 1: T060 (YOLO training guide)
Terminal 2: T061 (Database design guide)
Terminal 3: T062 (API development guide)
Terminal 4: T063-T064 (README + quickstart)
```

**Parallel Set 1** (after data prep T048-T049):
```
Terminal 1: T050-T052 (YOLO training - 2-4 hours GPU)
Terminal 2: T055-T056 (Custom Vision training - 1-2 hours)
Terminal 3: T046-T047 (Classifier class skeleton + wrapper)
```

**Parallel Set 2** (after T053 complete):
```
Terminal 1: T060 (Unit tests)
Terminal 2: T061 (Integration tests)
Terminal 3: T062 (Jupyter notebook)
Terminal 4: T063-T064 (Documentation guides)
```

### During Polish Phase

**Parallel Set** (T095-T110 all independent):
```
Terminal 1: T095-T100 (Products API endpoints)
Terminal 2: T108 (Azure setup guide)
Terminal 3: T109 (Database design guide)
Terminal 4: T110 (API development guide)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

For fastest time-to-value:
1. Complete T001-T024 (Setup + Foundational) - **2 weeks**
2. Complete T025-T045 (User Story 1) - **2 weeks**
3. Deploy and test MVP - **4 weeks total**

This delivers:
- Working out-of-stock detection
- Database persistence
- REST API
- Jupyter notebook demo
- Full documentation

### Incremental Delivery (All User Stories)

For complete learning experience:
1. Weeks 1-2: Setup + Foundational (T001-T024)
2. Weeks 3-4: User Story 1 (T025-T045)
3. Weeks 5-6: User Story 2 (T046-T066)
4. Weeks 7-8: User Story 3 + 4 (T067-T094) [parallel where possible]
5. Weeks 9-10: Polish + Testing (T095-T119)
6. Weeks 11-12: MLOps + Final Polish (T120-T126)

Each user story is independently testable at completion.

---

## Task Statistics

**Total Tasks**: 126

**By Phase**:
- Setup: 8 tasks (T001-T008)
- Foundational: 16 tasks (T009-T024)
- User Story 1: 21 tasks (T025-T045)
- User Story 2: 21 tasks (T046-T066)
- User Story 3: 13 tasks (T067-T079)
- User Story 4: 15 tasks (T080-T094)
- Polish: 32 tasks (T095-T126)

**Parallelizable Tasks**: ~60 tasks (48%) marked with [P]

**Independent User Stories**: 4 (Challenge 1-4), each with its own test criteria

**Estimated Duration**: 12 weeks (10 weeks ML + 2 weeks backend/polish)

---

## Success Criteria Mapping

| User Story | Tasks | Test Criteria | Metrics |
|------------|-------|---------------|---------|
| **US1: OOS Detection** | T025-T045 | Upload image → API returns gaps → DB contains results | Precision >90%, Recall >85% |
| **US2: Product Recognition** | T046-T066 | Upload image → API returns SKUs → DB links to products | mAP@0.5 >85%, Accuracy >90% |
| **US3: Stock Estimation** | T067-T079 | Submit analysis → API returns counts → DB aggregates | Count accuracy >90%, MAPE <15% |
| **US4: Price Verification** | T080-T094 | Upload image → API extracts prices → DB tracks history | OCR >95%, Extraction >90% |

---

## Notes

- **Database-First**: Complete T009-T018 (database setup) before any ML implementation
- **API Parallel to ML**: Implement API endpoints (T036-T037, T058, T072, T087) alongside ML modules
- **Sequential User Stories**: Complete each user story fully before next (prevents half-finished features)
- **Educational Focus**: Write documentation (T043, T063, T077, T092, T108-T110) immediately after implementation
- **Testing Pragmatism**: Unit tests for pure logic, integration tests for API, mock Azure calls
- **Constitution Compliance**: Keep functions <50 LOC, use type hints, educational error messages

**Status**: ✅ Task breakdown complete. Ready for implementation.

**Next Action**: Start with T001 (virtual environment setup) and work sequentially through Setup phase.
