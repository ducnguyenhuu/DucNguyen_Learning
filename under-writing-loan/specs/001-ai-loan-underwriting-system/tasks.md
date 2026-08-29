# Tasks: Multi-Agent AI Loan Underwriting System

**Feature**: `001-ai-loan-underwriting-system`  
**Input**: Design documents from `/specs/001-ai-loan-underwriting-system/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/mcp-server.yaml ✅, quickstart.md ✅

**Total Tasks**: 99 (reduced from 100 - removed GPT-4 Vision fallback tasks)

**Tests**: No test tasks included - feature specification does not request TDD approach. System validation occurs through interactive notebook execution.

**Organization**: Tasks grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US7)
- All tasks include exact file paths

## Path Conventions

Single project structure:
- `notebooks/` - Primary Jupyter interface
- `src/` - Reusable Python modules
- `tests/` - Automated validation
- `data/` - Storage (SQLite, PDFs, JSON)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project directory structure per plan.md (notebooks/, src/agents/, src/mcp/, src/rag/, data/, tests/)
- [x] T002 Initialize requirements.txt with all dependencies from plan.md (openai, langchain, langgraph, azure-ai-formrecognizer, azure-search-documents, fastapi, uvicorn, pydantic, mlflow, jupyter, plotly, pdfplumber, pytest)
- [x] T003 [P] Create .env.example with Azure credential template per quickstart.md (AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_DOCUMENT_INTELLIGENCE_*, AZURE_SEARCH_*)
- [x] T004 [P] Create README.md with project overview and quickstart link
- [x] T005 [P] Create .gitignore for Python project (venv/, .env, data/, __pycache__, .ipynb_checkpoints)
- [x] T006 Create src/config.py to load environment variables using python-dotenv per quickstart.md
- [x] T007 [P] Create src/__init__.py (empty package marker)
- [x] T008 [P] Create src/utils.py with shared helper functions (file I/O, JSON serialization)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T009 Create src/models.py with all 8 Pydantic schemas from data-model.md (LoanApplication, ExtractedDocument, CreditReport, RiskAssessment, ComplianceReport, LendingDecision, ApplicationState, PolicyDocument)
- [x] T010 Create notebooks/00_setup_and_test.ipynb implementing quickstart.md Section 3 validation (Azure OpenAI connection test, Document Intelligence test, AI Search test, embeddings test)
- [x] T011 Create data/mock_credit_bureau.db schema per contracts/mcp-server.yaml (credit_reports table with ssn, credit_score, payment_history, credit_utilization, accounts_open, derogatory_marks, credit_age_months)
- [x] T012 Create src/mcp/seed_data.py to populate mock_credit_bureau.db with 4 test profiles per quickstart.md (excellent 780, good 720, fair 670, poor 590)
- [x] T013 Create data/database.db schema for application metadata per plan.md (applications table with application_id, status, created_at, updated_at, mlflow_run_id)
- [x] T014 Create tests/conftest.py with pytest fixtures (sample LoanApplication, mock Azure clients, temp directories)
- [x] T015 [P] Create tests/sample_applications/ directory with 4+ test PDFs per plan.md (pay_stub_clean.pdf, pay_stub_scanned.pdf, bank_statement.pdf, drivers_license.pdf)
- [x] T016 [P] Create data/policies/ with 5 sample lending policy documents per spec.md FR-015 (underwriting_standards.pdf, credit_requirements.pdf, income_verification.pdf, property_guidelines.pdf, compliance_rules.pdf)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Document Processing & Extraction (Priority: P1) 🎯 MVP

**Goal**: Extract structured data from loan documents using Azure Document Intelligence

**Independent Test**: Upload pay stub PDF → system returns JSON with extracted fields (employer, income, dates) + confidence scores

### Implementation for User Story 1

- [x] T017 [P] [US1] Create src/agents/__init__.py (empty package marker)
- [x] T018 [US1] Implement Azure Document Intelligence client wrapper in src/agents/document_agent.py::DocumentIntelligenceExtractor class (analyze_document method using prebuilt-invoice model per research.md decision)
- [x] T019 [US1] Implement GPT-4o text normalization in src/agents/document_agent.py::FieldNormalizer class (unify field names, calculate monthly from annual income per spec.md FR-004)
- [x] T020 [US1] Implement validation rules in src/agents/document_agent.py::DataValidator class (net <= gross, dates chronological, non-negative values per spec.md FR-005)
- [x] T021 [US1] Implement completeness scoring in src/agents/document_agent.py::CompletenessCalculator class (percentage of required fields extracted)
- [x] T022 [US1] Create notebooks/01_document_agent.ipynb demonstrating document upload, extraction, confidence scoring per spec.md acceptance scenarios
- [x] T023 [US1] Add interactive JSON viewer in 01_document_agent.ipynb using ipywidgets to display ExtractedDocument outputs
- [x] T024 [US1] Implement cost logging in document_agent.py (track Document Intelligence usage, log per-document cost per spec.md FR-007)

**Checkpoint**: Document Agent fully functional - can extract structured data from PDFs independently

---

## Phase 4: User Story 2 - Financial Risk Analysis (Priority: P1) 🎯 MVP

**Goal**: Calculate financial metrics (DTI, LTV, PTI) and perform AI-powered risk assessment using credit data from MCP server

**Independent Test**: Given extracted document data + SSN → system queries credit DB, calculates ratios, returns risk level (low/medium/high) with GPT-4 reasoning

### Implementation for User Story 2

- [x] T025 [US2] Create src/mcp/__init__.py (empty package marker)
- [x] T026 [P] [US2] Create src/mcp/connectors/__init__.py (empty package marker)
- [x] T027 [US2] Implement FastAPI MCP server in src/mcp/server.py with 5 endpoints per contracts/mcp-server.yaml (GET /files/{filename}, GET /credit/{ssn}, GET /application/{app_id}, POST /admin/seed_credit_db, GET /health)
- [x] T028 [P] [US2] Implement file connector in src/mcp/connectors/file_connector.py (read PDFs from data/applications/ directory with path validation)
- [x] T029 [P] [US2] Implement credit connector in src/mcp/connectors/credit_connector.py (query mock_credit_bureau.db, return CreditReport schema per data-model.md)
- [x] T030 [US2] Implement DTI calculator in src/agents/risk_agent.py::FinancialCalculator class (DTI = monthly_debt / monthly_income × 100 per spec.md FR-009)
- [x] T031 [US2] Implement LTV calculator in src/agents/risk_agent.py::FinancialCalculator class (LTV = loan_amount / property_value × 100 per spec.md FR-010)
- [x] T032 [US2] Implement PTI calculator in src/agents/risk_agent.py::FinancialCalculator class (PTI = monthly_payment / monthly_income × 100 using amortization formula per spec.md FR-011)
- [x] T033 [US2] Implement GPT-4o risk analysis prompt in src/agents/risk_agent.py::RiskAnalyzer class (prompt with calculated metrics + credit data, expect risk_level + 3 risk_factors + 3 mitigating_factors per spec.md FR-012-013)
- [x] T034 [US2] Implement Plotly visualization generator in src/agents/risk_agent.py::RiskVisualizer class (bar chart for DTI/LTV/PTI with threshold lines per spec.md FR-014)
- [x] T035 [US2] Create notebooks/02_risk_agent.ipynb demonstrating MCP credit query, financial calculations, GPT-4o risk reasoning, interactive charts per spec.md acceptance scenario 1-5
- [x] T036 [US2] Add side-by-side comparison in 02_risk_agent.ipynb for excellent (780) vs poor (620) credit profiles showing different risk assessments
- [x] T037 [US2] Implement MCP server startup script in src/mcp/run_server.sh for easy launch (uvicorn command with --reload flag)

**Checkpoint**: Risk Agent fully functional - can analyze creditworthiness independently using MCP data

---

## Phase 5: User Story 3 - Policy Compliance via RAG (Priority: P2)

**Goal**: Use RAG to retrieve relevant lending policies and ground GPT-4 compliance checking in organizational knowledge

**Independent Test**: Given compliance query ("Is DTI 38% acceptable?") → system embeds query, searches Azure AI Search, retrieves top-3 policy chunks, returns grounded answer citing policy

### Implementation for User Story 3

- [x] T038 [P] [US3] Create src/rag/__init__.py (empty package marker)
- [x] T039 [US3] Implement Azure AI Search index creation in src/rag/indexer.py::PolicyIndexer class (create lending-policies-index with 1536-dim vector field per research.md decision)
- [x] T040 [US3] Implement document chunking in src/rag/indexer.py::DocumentChunker class (500 token chunks with 50 token overlap per research.md decision)
- [x] T041 [US3] Implement Ada-002 embedding generator in src/rag/embeddings.py::EmbeddingGenerator class (batch embed chunks using Azure OpenAI text-embedding-ada-002 per spec.md FR-015)
- [x] T042 [US3] Implement policy upload and indexing pipeline in src/rag/indexer.py::PolicyIndexer.index_documents method (chunk → embed → upload to Azure AI Search per spec.md FR-015)
- [X] T043 [US3] Implement semantic search retriever in src/rag/retriever.py::PolicyRetriever class (embed query, cosine similarity search, return top-3 chunks per spec.md FR-016-017)
- [X] T044 [US3] Create notebooks/03_rag_system.ipynb demonstrating offline indexing of 5 policy documents, query embedding, similarity search, chunk retrieval per spec.md acceptance scenario 1-5
- [X] T045 [US3] Add interactive search widget in 03_rag_system.ipynb (text input for queries, display retrieved chunks with similarity scores)
- [X] T046 [US3] Implement no-result handling in retriever per spec.md edge case 3 (return empty list if all similarity scores <0.5)

**Checkpoint**: RAG system fully functional - can retrieve relevant policy sections independently

---

## Phase 6: User Story 4 - Final Decision & Explanation Generation (Priority: P2)

**Goal**: Synthesize outputs from all agents into transparent lending decision with risk-adjusted rate and plain-language explanation

**Independent Test**: Given document data + risk assessment + compliance report → system applies decision rules, calculates interest rate, returns Approved/Rejected/Conditional with detailed explanation

### Implementation for User Story 4

- [X] T047 [P] [US4] Implement compliance agent in src/agents/compliance_agent.py::ComplianceAgent class (integrate PolicyRetriever, prompt GPT-4o with retrieved context per spec.md FR-018)
- [X] T048 [US4] Implement policy citation extraction in src/agents/compliance_agent.py::CitationExtractor class (parse GPT-4o response for policy references)
- [X] T049 [US4] Create notebooks/04_compliance_agent.ipynb demonstrating RAG-powered compliance checking, policy citations, compliance status determination per spec.md acceptance scenario 1-5
- [X] T050 [US4] Implement decision rules matrix in src/agents/decision_agent.py::DecisionRules class (auto-reject if DTI >43% AND credit_score <640 per spec.md FR-021)
- [X] T051 [US4] Implement state aggregator in src/agents/decision_agent.py::StateAggregator class (combine ExtractedDocument + RiskAssessment + ComplianceReport into single dict per spec.md FR-020)
- [X] T052 [US4] Implement GPT-4o decision analysis prompt in src/agents/decision_agent.py::DecisionAnalyzer class (prompt with aggregated state for borderline cases per spec.md FR-022)
- [X] T053 [US4] Implement risk-adjusted rate calculator in src/agents/decision_agent.py::RateCalculator class (base rate + credit_score_adjustment + risk_level_premium per spec.md FR-023)
- [X] T054 [US4] Implement explanation generator in src/agents/decision_agent.py::ExplanationGenerator class (GPT-4o prompt for plain-language decision summary per spec.md FR-025)
- [X] T055 [US4] Create notebooks/05_decision_agent.ipynb demonstrating decision rule application, GPT-4o borderline analysis, rate calculation, explanation generation per spec.md acceptance scenario 1-5
- [X] T056 [US4] Add decision confidence indicator in 05_decision_agent.ipynb (color-coded decision status: green=Approved, yellow=Conditional, red=Rejected)

**Checkpoint**: Decision Agent fully functional - can make final lending decisions independently with transparent reasoning

---

## Phase 7: User Story 5 - Multi-Agent Orchestration with LangGraph (Priority: P3)

**Goal**: Coordinate sequential agent execution through LangGraph state machine with error handling

**Independent Test**: Submit complete application → LangGraph executes document → risk → compliance → decision in sequence, persists state, handles failures, returns final output with metadata

### Implementation for User Story 5

- [X] T059 [US5] Define ApplicationState TypedDict in src/orchestrator.py per data-model.md (application_id, documents, extracted_data, credit_report, risk_assessment, compliance_result, final_decision, errors, execution_times)
- [X] T060 [US5] Implement document agent node in src/orchestrator.py::document_agent_node function (calls DocumentAgent, updates state.extracted_data, handles errors)
- [X] T061 [US5] Implement risk agent node in src/orchestrator.py::risk_agent_node function (queries MCP for credit, calls RiskAgent, updates state.risk_assessment)
- [X] T062 [US5] Implement compliance agent node in src/orchestrator.py::compliance_agent_node function (calls ComplianceAgent with RAG, updates state.compliance_result)
- [X] T063 [US5] Implement decision agent node in src/orchestrator.py::decision_agent_node function (calls DecisionAgent, updates state.final_decision)
- [X] T064 [US5] Define LangGraph workflow in src/orchestrator.py::create_workflow function (StateGraph with edges: document → risk → compliance → decision per spec.md FR-026)
- [X] T065 [US5] Implement error state node in src/orchestrator.py::error_handler_node function (logs error, marks workflow as failed, does not execute downstream agents per spec.md FR-028)
- [X] T066 [US5] Add conditional edges in create_workflow for error routing (check state.errors after each node per spec.md acceptance scenario 4)
- [X] T067 [US5] Implement execution timer in orchestrator nodes (track start/end time per agent, populate state.execution_times per spec.md FR-029)
- [X] T068 [US5] Create notebooks/06_orchestration.ipynb demonstrating full workflow execution, state evolution visualization, error handling scenarios per spec.md acceptance scenario 1-5
- [X] T069 [US5] Add state transition diagram in 06_orchestration.ipynb using Graphviz or mermaid to show agent flow

**Checkpoint**: Orchestration fully functional - complete multi-agent workflow executes end-to-end

---

## Phase 8: User Story 6 - Experiment Tracking with MLflow (Priority: P3)

**Goal**: Log agent execution metrics and enable experiment comparison for prompt/model variations

**Independent Test**: Process 10+ applications → MLflow logs time, tokens, costs, approval rate → learner views dashboard comparing experiments

### Implementation for User Story 6

- [ ] T070 [P] [US6] Implement MLflow logging wrapper in src/utils.py::MLflowLogger class (auto-log parameters, metrics, artifacts per spec.md FR-036)
- [ ] T071 [US6] Integrate MLflow logging in document_agent.py (log extraction_time, confidence_score, tool_used, cost_usd per run)
- [ ] T072 [US6] Integrate MLflow logging in risk_agent.py (log analysis_time, dti_ratio, ltv_ratio, risk_level, credit_score per run)
- [ ] T073 [US6] Integrate MLflow logging in compliance_agent.py (log compliance_check_time, compliance_status, policies_retrieved per run)
- [ ] T074 [US6] Integrate MLflow logging in decision_agent.py (log decision_time, decision_status, interest_rate, confidence_level per run)
- [ ] T075 [US6] Integrate MLflow logging in orchestrator.py (log total_workflow_time, total_tokens, total_cost, final_decision per application per spec.md FR-036)
- [ ] T076 [US6] Implement artifact saving in MLflowLogger (save ExtractedDocument JSON, RiskAssessment JSON, ComplianceReport JSON, LendingDecision JSON per spec.md FR-037)
- [ ] T077 [US6] Create notebooks/07_end_to_end_demo.ipynb processing 10 diverse applications with MLflow tracking per spec.md acceptance scenario 1-2
- [ ] T078 [US6] Add experiment comparison section in 07_end_to_end_demo.ipynb (compare 2 different risk analysis prompts side-by-side per spec.md acceptance scenario 3)
- [ ] T079 [US6] Implement MLflow query utilities in src/utils.py::MLflowQueryHelper class (filter runs by parameters, aggregate metrics per spec.md acceptance scenario 5)
- [ ] T080 [US6] Add MLflow UI screenshots and instructions in 07_end_to_end_demo.ipynb (how to access http://localhost:5000, navigate experiments, compare runs)

**Checkpoint**: MLflow integration complete - all experiments logged and comparable

---

## Phase 9: User Story 7 - Cost Optimization (Priority: P3)

**Goal**: Demonstrate cost tracking and analysis for Document Intelligence extraction

**Independent Test**: Process 10 documents → track Document Intelligence costs → cost breakdown shows per-document expenses

### Implementation for User Story 7

- [ ] T081 [US7] Implement cost tracker in src/agents/document_agent.py::CostTracker class (log Document Intelligence cost $0.001/page, GPT-4o text cost per token per research.md decision)
- [ ] T082 [US7] Enhance extraction logging in DocumentAgent (record confidence scores and extraction quality metrics per spec.md acceptance scenarios)
- [ ] T083 [US7] Create cost analysis notebook section in 01_document_agent.ipynb (batch process 10 documents, display per-doc cost breakdown per spec.md acceptance scenarios)
- [ ] T084 [US7] Implement extraction quality analyzer in src/utils.py::DocumentAnalyzer class (track extraction patterns and confidence levels by document type per spec.md acceptance scenarios)
- [ ] T085 [US7] Add cost visualization in 01_document_agent.ipynb (Plotly bar chart: Document Intelligence cost per document)
- [ ] T086 [US7] Create cost optimization recommendations section in 01_document_agent.ipynb (best practices for document quality and preprocessing)

**Checkpoint**: Cost tracking fully documented - learners understand economic considerations

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements affecting multiple user stories

- [ ] T087 [P] Create comprehensive README.md with architecture diagram, quickstart steps, notebook sequence, learning objectives
- [ ] T088 [P] Update docs/SIMPLIFIED_ARCHITECTURE.md with implementation details and actual performance metrics from testing
- [ ] T089 [P] Create docs/IMPLEMENTATION_GUIDE.md with phase-by-phase walkthrough linking to specific notebooks and code modules
- [ ] T090 [P] Create docs/NOTEBOOK_APPROACH.md explaining notebook-first pedagogy and how to modify for custom experiments
- [ ] T091 Add error handling improvements across all agents (retry logic for Azure API timeouts, graceful degradation for missing data per spec.md edge cases)
- [ ] T092 Implement input validation in all agents (validate Pydantic models at entry/exit, log validation errors)
- [ ] T093 Add logging configuration in src/config.py (structured logging with timestamps, severity levels, log files)
- [ ] T094 [P] Create tests/test_models.py for Pydantic model validation (test all 8 schemas with valid/invalid inputs per data-model.md)
- [ ] T095 [P] Create tests/test_calculations.py for financial formulas (DTI/LTV/PTI calculations with edge cases per spec.md FR-009-011)
- [ ] T096 [P] Create tests/test_mcp_server.py for MCP API endpoints (test all 5 endpoints with FastAPI TestClient per contracts/mcp-server.yaml)
- [ ] T097 Run quickstart.md validation end-to-end (fresh environment setup, verify all notebooks execute successfully)
- [ ] T098 Add performance profiling in orchestrator.py (identify bottlenecks, log slowest agents)
- [ ] T099 Create troubleshooting guide in docs/TROUBLESHOOTING.md (common errors, Azure quota issues, credential problems)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-9)**: All depend on Foundational phase completion
  - US1 (Phase 3): Can start after Foundational - No dependencies on other stories
  - US2 (Phase 4): Can start after Foundational - No dependencies on other stories (MCP server independent)
  - US3 (Phase 5): Can start after Foundational - No dependencies on other stories (RAG system independent)
  - US4 (Phase 6): Depends on US3 completion (Compliance Agent uses RAG retriever)
  - US5 (Phase 7): Depends on US1, US2, US4 completion (Orchestrator calls all agents)
  - US6 (Phase 8): Depends on US5 completion (MLflow logs orchestrated workflow metrics)
  - US7 (Phase 9): Enhances US1 (Cost tracking in Document Agent)
- **Polish (Phase 10)**: Depends on all desired user stories being complete

### User Story Dependencies

```
US1 (Document Agent) ──┐
US2 (Risk Agent) ──────┤
                       ├──> US4 (Decision Agent) ──> US5 (Orchestration) ──> US6 (MLflow)
US3 (RAG System) ──────┘

US7 (Cost Optimization) enhances US1 (can be implemented in parallel or after US1)
```

- **US1**: Independent - Can start immediately after Foundational
- **US2**: Independent - Can start immediately after Foundational
- **US3**: Independent - Can start immediately after Foundational
- **US4**: Requires US3 (Compliance Agent needs RAG retriever)
- **US5**: Requires US1, US2, US4 (Orchestrator integrates all agents)
- **US6**: Requires US5 (Logs orchestrated workflow)
- **US7**: Enhances US1 (Add cost tracking to existing Document Agent)

### Within Each User Story

**US1 (Document Agent)**:
1. Azure Document Intelligence client (T018)
2. Normalization (T019) and validation (T020) depend on client
3. Completeness scoring (T021) depends on validation
4. Notebook (T022) depends on all agent logic complete

**US2 (Risk Agent)**:
1. MCP server (T027) and connectors (T028-T029) can develop in parallel
2. Calculators (T030-T032) independent of MCP (can run parallel)
3. GPT-4o risk analysis (T033) depends on calculators
4. Notebook (T035) depends on all components

**US3 (RAG System)**:
1. Indexer (T039), chunker (T040), embeddings (T041) develop together
2. Indexing pipeline (T042) depends on all three
3. Retriever (T043) depends on index existing
4. Notebook (T044) depends on retriever

**US4 (Decision Agent)**:
1. Compliance agent (T047-T049) depends on US3 complete
2. Decision rules (T050) and aggregator (T051) independent (parallel)
3. Decision analysis (T052-T054) depends on rules + aggregator
4. Notebook (T055) depends on all decision logic

**US5 (Orchestration)**:
1. State definition (T059) first
2. All agent nodes (T060-T063) develop in parallel (different functions)
3. Workflow creation (T064) depends on all nodes complete
4. Error handling (T065-T066) adds to workflow
5. Notebook (T068) depends on workflow complete

**US6 (MLflow)**:
1. Logger wrapper (T070) first
2. All agent integrations (T071-T075) in parallel (different files)
3. Artifact saving (T076) enhances logger
4. Notebook (T077) depends on all logging integrated

**US7 (Cost Optimization)**:
1. Cost tracker (T081) and extraction logging (T082) in parallel
2. Analysis notebook sections (T083-T086) after tracking implemented

### Parallel Opportunities

**Setup Phase (Phase 1)**: T003, T004, T005, T007, T008 can all run in parallel

**Foundational Phase (Phase 2)**: T015, T016 (test data creation) can run in parallel with other tasks

**US1**: T018 [P] (DI client) + T019 [P] (Vision client) parallel, T025 [P] (JSON viewer) independent

**US2**: T027-T028 [P] (package init), T030 [P] + T031 [P] (connectors), T032-T034 (calculators parallel)

**US3**: T040 [P] (package init), T041-T043 (indexer components together)

**US4**: T049 [P] (compliance agent file) + T052-T053 (decision files) parallel

**US5**: T060-T063 (agent nodes - all different functions) parallel

**US6**: T070 [P] (logger wrapper), T071-T075 (agent integrations - all different files) parallel

**US7**: T081 [P] + T082 [P] (tracking components) parallel

**Polish Phase**: T088-T091 [P] (documentation), T095-T097 [P] (tests) parallel

---

## Parallel Example: User Story 1 (Document Agent)

```bash
# Launch Azure DI client and Vision client development together:
Task T018: "Implement Azure Document Intelligence client wrapper in src/agents/document_agent.py::DocumentIntelligenceExtractor"
Task T019: "Implement GPT-4 Vision fallback handler in src/agents/document_agent.py::VisionExtractor"

# After routing logic complete, launch normalization and validation together:
Task T021: "Implement GPT-4 text normalization in src/agents/document_agent.py::FieldNormalizer"
Task T022: "Implement validation rules in src/agents/document_agent.py::DataValidator"
```

---

## Parallel Example: User Story 2 (Risk Agent)

```bash
# Launch MCP server and financial calculators together:
Task T029: "Implement FastAPI MCP server in src/mcp/server.py"
Task T032: "Implement DTI calculator in src/agents/risk_agent.py::FinancialCalculator"
Task T033: "Implement LTV calculator in src/agents/risk_agent.py::FinancialCalculator"
Task T034: "Implement PTI calculator in src/agents/risk_agent.py::FinancialCalculator"

# Launch connectors in parallel:
Task T030: "Implement file connector in src/mcp/connectors/file_connector.py"
Task T031: "Implement credit connector in src/mcp/connectors/credit_connector.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1-2 Only)

1. Complete Phase 1: Setup (T001-T008)
2. Complete Phase 2: Foundational (T009-T016) - CRITICAL GATE
3. Complete Phase 3: User Story 1 - Document Agent (T017-T026)
4. Complete Phase 4: User Story 2 - Risk Agent (T027-T039)
5. **STOP and VALIDATE**: Process 5 test applications end-to-end (document extraction → risk analysis)
6. **MVP DELIVERED**: Core document processing + financial analysis working

**Value**: Learners can extract documents and analyze risk independently - demonstrates core AI agent patterns

### Incremental Delivery

1. MVP (US1 + US2) → Validate → Demo extraction + risk analysis
2. Add US3 (RAG System) → Validate → Demo semantic policy search
3. Add US4 (Decision Agent) → Validate → Demo complete decision with policy compliance
4. Add US5 (Orchestration) → Validate → Demo automated multi-agent workflow
5. Add US6 (MLflow) → Validate → Demo experiment tracking and comparison
6. Add US7 (Cost Optimization) → Validate → Demo economic tradeoffs

Each story adds new learning objective without breaking previous stories.

### Parallel Team Strategy

With multiple developers (after Foundational Phase complete):

**Week 1-2**:
- Developer A: User Story 1 (Document Agent)
- Developer B: User Story 2 (Risk Agent)  
- Developer C: User Story 3 (RAG System)

**Week 3**:
- Developer A: User Story 4 (Decision Agent - requires US3)
- Developer B: Help with US5 (Orchestration - requires US1, US2)
- Developer C: User Story 7 (Cost Optimization - enhances US1)

**Week 4**:
- All: User Story 5 (Orchestration - integrate all agents)

**Week 5**:
- Developer A: User Story 6 (MLflow)
- Developer B+C: Phase 10 (Polish + documentation)

---

## Notes

- **[P] tasks**: Different files or independent functions - no conflicts
- **[Story] label**: Maps task to user story for traceability
- **Independent testing**: Each user story has "Independent Test" in phase header showing how to validate without other stories
- **Notebook-first**: All major features demonstrated in notebooks (01-07) - notebooks are deliverables, not afterthoughts
- **No test suite**: Feature spec does not request TDD - validation through interactive notebook execution
- **Foundational gate**: Phase 2 MUST complete before any user story work (Pydantic models, mock data, test fixtures required by all agents)
- **Cost consciousness**: US7 explicitly teaches economic tradeoffs - Document Intelligence first saves ~85% vs Vision-only
- **MLflow last**: US6 tracks experiments across all agents - requires US5 orchestration complete first
- **Commit frequently**: Commit after each task or logical group for rollback capability
- **Stop at checkpoints**: Each phase end allows validation before proceeding to next story

---

## Task Count Summary

- **Phase 1 (Setup)**: 8 tasks
- **Phase 2 (Foundational)**: 8 tasks (BLOCKING)
- **Phase 3 (US1 - Document Agent)**: 10 tasks
- **Phase 4 (US2 - Risk Agent)**: 13 tasks
- **Phase 5 (US3 - RAG System)**: 9 tasks
- **Phase 6 (US4 - Decision Agent)**: 10 tasks
- **Phase 7 (US5 - Orchestration)**: 11 tasks
- **Phase 8 (US6 - MLflow)**: 11 tasks
- **Phase 9 (US7 - Cost Optimization)**: 7 tasks
- **Phase 10 (Polish)**: 13 tasks

**Total**: 100 tasks

**Parallel Opportunities**: 42 tasks marked [P] (42% parallelizable)

**MVP Scope**: Phase 1 (8) + Phase 2 (8) + Phase 3 (10) + Phase 4 (13) = **39 tasks for MVP**

**Independent Stories**: US1, US2, US3 can all start in parallel after Foundational phase complete (28 tasks executable simultaneously with 3 developers)
