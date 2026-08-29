# Implementation Plan: Multi-Agent AI Loan Underwriting System

**Branch**: `001-ai-loan-underwriting-system` | **Date**: November 19, 2025 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `/specs/001-ai-loan-underwriting-system/spec.md`

## Summary

Build an educational multi-agent AI system for loan underwriting that teaches learners about AI agent orchestration, Gen AI reasoning, hybrid OCR strategies, RAG (Retrieval Augmented Generation), and MCP (Model Context Protocol) integration. The system processes loan applications through four specialized agents (Document, Risk, Compliance, Decision) coordinated by LangGraph, using Azure OpenAI services, with Jupyter notebooks as the primary development interface.

**Primary Requirement**: Enable learners to understand multi-agent AI systems through hands-on experimentation with document processing, financial analysis, policy compliance checking, and transparent decision-making.

**Technical Approach**: 
- Hybrid OCR: Azure Document Intelligence (primary, cost-effective) with GPT-4 Vision fallback for edge cases
- Multi-agent architecture: Independent agents with clear responsibilities, coordinated via LangGraph state machine
- RAG implementation: Azure AI Search vector database for semantic policy retrieval
- MCP pattern: FastAPI server abstracting data access (filesystem, SQLite mock credit DB)
- Notebook-first development: Jupyter notebooks for each phase enabling interactive learning and visualization

## Technical Context

**Language/Version**: Python 3.10+  
**Primary Dependencies**: 
- AI/ML: `openai` (Azure OpenAI SDK), `langchain`, `langgraph`, `azure-ai-formrecognizer` (Document Intelligence), `azure-search-documents` (AI Search)
- Data: `pydantic` (v2), `sqlite3` (stdlib), `pandas` (optional analysis)
- API: `fastapi`, `uvicorn` (MCP server)
- Notebooks: `jupyter`, `ipykernel`, `ipywidgets`
- Visualization: `plotly`, `matplotlib`
- Utils: `pdfplumber`, `python-dotenv`, `httpx`
- Tracking: `mlflow`

**Storage**: 
- Local filesystem for uploaded PDFs (`data/applications/`)
- SQLite for mock credit bureau data (`data/mock_credit_bureau.db`)
- SQLite for application metadata (`data/database.sqlite`)
- JSON files for extracted data (`data/extracted/`)
- Azure AI Search (cloud) for RAG vector storage

**Testing**: 
- `pytest` for unit tests (financial calculations, data validation)
- `pytest-asyncio` for async MCP server tests
- Notebook execution tests via `nbconvert` or manual validation
- Sample documents and test profiles for integration testing

**Target Platform**: 
- Local development: macOS/Linux/Windows workstation
- Single-machine deployment (no distributed system requirements)
- Jupyter notebook environment (JupyterLab or VS Code notebooks)

**Project Type**: Research/Educational project - single monorepo with notebooks as primary interface

**Performance Goals**: 
- Document extraction: <10 seconds per standard PDF (via Document Intelligence)
- Complete 4-agent workflow: <60 seconds per application
- RAG retrieval: <2 seconds for policy search
- Support 10+ applications in single notebook session without restart

**Constraints**: 
- Educational focus: Clarity and learning experience over production optimization
- Cost-conscious: Document Intelligence first (~$0.001/page) before Vision (~$0.02/image)
- No production security: Mock data, local-only, no real PII
- Notebook-first: All features must be demonstrable and testable in Jupyter
- Single machine: No distributed system complexity

**Scale/Scope**: 
- 4 specialized AI agents (Document, Risk, Compliance, Decision)
- 7-8 Jupyter notebooks (setup, document, risk, RAG, compliance, decision, orchestration, demo)
- 5-10 policy documents indexed in RAG
- 4+ mock credit profiles for testing
- 20+ sample test applications for validation
- Single learner environment (no multi-user)

## Constitution Check

*GATE: Educational project with template constitution - no specific gates defined. Proceeding with standard best practices.*

**Constitution Status**: Template only - no project-specific principles defined yet.

**Standard Best Practices Applied**:
- ✅ **Simplicity**: Start with minimal viable components, add complexity only when needed for learning objectives
- ✅ **Modularity**: Each agent independently testable in its own notebook
- ✅ **Observability**: Clear logging, intermediate outputs visible in notebooks, MLflow tracking
- ✅ **Documentation**: Each notebook self-documenting with markdown cells explaining concepts
- ✅ **Reproducibility**: Seed data, fixed test cases, environment configuration template

**Re-check after Phase 1**: Verify data models and contracts maintain educational clarity and don't introduce unnecessary complexity.

## Project Structure

### Documentation (this feature)

```text
specs/001-ai-loan-underwriting-system/
├── spec.md              # Feature specification ✅ Created
├── plan.md              # This file (implementation plan)
├── research.md          # Phase 0: Technology research and decisions
├── data-model.md        # Phase 1: Pydantic schemas and entity definitions
├── quickstart.md        # Phase 1: Setup guide and first run instructions
├── contracts/           # Phase 1: MCP API contracts (OpenAPI)
│   └── mcp-server.yaml  # FastAPI endpoint specifications
└── checklists/
    └── requirements.md  # Quality validation ✅ Created
```

### Source Code (repository root)

```text
under-writing-loan/
├── .env.example                    # Environment variables template
├── requirements.txt                # Python dependencies
├── README.md                       # Project overview
│
├── notebooks/                      # PRIMARY INTERFACE - Jupyter notebooks
│   ├── 00_setup_and_test.ipynb    # ✅ Created - Azure connection tests
│   ├── 01_document_agent.ipynb    # ✅ Created - OCR extraction pipeline
│   ├── 02_risk_agent.ipynb        # 🔄 Next - Financial analysis + MCP
│   ├── 03_rag_system.ipynb        # RAG indexing and retrieval
│   ├── 04_compliance_agent.ipynb  # Policy compliance checking
│   ├── 05_decision_agent.ipynb    # Final decision + explanations
│   ├── 06_orchestration.ipynb     # LangGraph multi-agent workflow
│   └── 07_end_to_end_demo.ipynb   # Full pipeline + MLflow comparison
│
├── src/                            # Reusable Python modules
│   ├── __init__.py
│   ├── models.py                   # Pydantic data models (from data-model.md)
│   ├── config.py                   # Environment configuration
│   ├── utils.py                    # Shared utilities
│   │
│   ├── agents/                     # AI Agent implementations
│   │   ├── __init__.py
│   │   ├── document_agent.py       # OCR + extraction logic
│   │   ├── risk_agent.py           # Financial calculations + GPT-4 analysis
│   │   ├── compliance_agent.py     # RAG-powered policy checking
│   │   └── decision_agent.py       # Final decision + explanations
│   │
│   ├── mcp/                        # Model Context Protocol server
│   │   ├── __init__.py
│   │   ├── server.py               # FastAPI application
│   │   ├── seed_data.py            # Populate mock databases
│   │   └── connectors/             # Data source connectors
│   │       ├── __init__.py
│   │       ├── file_connector.py   # Filesystem access
│   │       └── credit_connector.py # Mock credit database
│   │
│   ├── rag/                        # Retrieval Augmented Generation
│   │   ├── __init__.py
│   │   ├── indexer.py              # Policy document indexing
│   │   ├── retriever.py            # Semantic search
│   │   └── embeddings.py           # Ada-002 embedding utilities
│   │
│   └── orchestrator.py             # LangGraph workflow definition
│
├── data/                           # Data storage (gitignored except samples)
│   ├── applications/               # Uploaded PDF documents
│   ├── extracted/                  # Extracted JSON outputs
│   ├── policies/                   # Policy documents for RAG
│   ├── database.sqlite             # Application metadata
│   └── mock_credit_bureau.db       # Mock credit profiles
│
├── tests/                          # Automated tests
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   ├── test_models.py              # Pydantic model validation
│   ├── test_calculations.py        # DTI/LTV/PTI formulas
│   ├── test_mcp_server.py          # MCP API endpoints
│   └── sample_applications/        # Test data
│       ├── pay_stub_clean.pdf
│       ├── pay_stub_scanned.pdf
│       ├── bank_statement.pdf
│       └── test_profiles.json
│
├── docs/                           # Architecture documentation
│   ├── SIMPLIFIED_ARCHITECTURE.md  # ✅ Created - System design
│   ├── IMPLEMENTATION_GUIDE.md     # Phase-by-phase guide
│   └── NOTEBOOK_APPROACH.md        # Notebook learning path
│
└── .specify/                       # Spec tooling
    └── memory/
        └── constitution.md         # Project principles (template)
```

**Structure Decision**: Single monorepo with notebook-first development. Source code in `src/` provides reusable modules imported by notebooks, enabling learners to focus on concepts in notebooks while maintaining clean, testable Python modules. No frontend/backend split needed - notebooks serve as interactive UI.

## Complexity Tracking

> No constitution violations to track - educational project with appropriate scope for learning objectives.

| Complexity Item | Justification | Simpler Alternative Considered |
|-----------------|---------------|--------------------------------|
| 4 AI agents | Each agent teaches distinct concept: OCR (Document), calculations+MCP (Risk), RAG (Compliance), explainability (Decision). Merging would dilute learning objectives. | Single "do everything" agent - rejected because learners wouldn't understand separation of concerns and agent orchestration patterns |
| LangGraph orchestration | Demonstrates production-ready multi-agent coordination with state management - critical learning objective for advanced workflow patterns. | Manual sequential calls - rejected because learners need to understand stateful orchestration and error handling in real systems |
| Hybrid OCR (DI + Vision) | Teaches cost optimization and fallback strategies - practical real-world concern. Vision-only would cost 10x more; DI-only would fail on edge cases. | Single OCR tool - rejected because doesn't teach decision-making between tools based on quality/cost tradeoffs |
| MCP abstraction layer | Teaches data access protocol pattern - prepares learners for real API integration. Direct database access in agents would couple business logic to storage. | Direct SQLite calls in agents - rejected because poor separation of concerns and difficult to swap for real credit bureau later |

---

## Phase 0: Research & Technology Decisions

**Prerequisites**: Feature specification complete

**Objective**: Resolve technical unknowns and document technology choices with rationale

### Research Tasks

1. **Azure Document Intelligence prebuilt models evaluation**
   - Research: Which prebuilt models support pay stubs, bank statements, tax returns, IDs?
   - Decision criteria: Model availability, field extraction capabilities, confidence scoring
   - Output: Model selection matrix mapping document types to prebuilt models

2. **GPT-4 Vision vs Document Intelligence cost analysis**
   - Research: Exact pricing per page/image, processing speed, quality differences
   - Decision criteria: Cost per document, accuracy on sample documents, latency
   - Output: Cost comparison table and fallback threshold recommendation (0.7 confidence)

3. **LangGraph state management patterns**
   - Research: Best practices for ApplicationState design, error handling, agent communication
   - Decision criteria: Code clarity, error recovery, educational value
   - Output: State schema design with transition rules

4. **Azure AI Search free tier limitations**
   - Research: Document limits, query throughput, vector dimensions, hybrid search support
   - Decision criteria: Sufficient for 5-10 policy docs, educational use case
   - Output: Index configuration and chunking strategy

5. **MLflow local setup for educational use**
   - Research: Tracking server setup, artifact storage, experiment comparison UI
   - Decision criteria: Zero-config local deployment, notebook integration
   - Output: MLflow configuration and logging patterns

6. **Pydantic v2 best practices for LLM outputs**
   - Research: JSON mode vs function calling, retry strategies, validation patterns
   - Decision criteria: Reliability, ease of debugging for learners
   - Output: Pydantic model patterns and GPT-4 prompting strategies

**Deliverable**: `research.md` with documented decisions, alternatives considered, rationale for each choice

---

## Phase 1: Design & Contracts

**Prerequisites**: `research.md` complete, all NEEDS CLARIFICATION resolved

**Objective**: Define data models, API contracts, and setup instructions

### 1.1 Data Model Design (`data-model.md`)

Extract entities from specification and define Pydantic schemas:

**Core Entities**:

1. **LoanApplication**
   - Fields: `application_id`, `applicant_name`, `ssn`, `loan_amount`, `property_value`, `annual_income`, `document_paths`, `created_at`, `status`
   - Validation: Loan amount > 0, property value > loan amount (for LTV <100%), SSN format
   - State transitions: Draft → Processing → Completed/Error

2. **ExtractedDocument**
   - Fields: `document_id`, `document_type` (enum: pay_stub/bank_statement/tax_return/id), `extracted_fields` (dict), `confidence_scores` (dict[str, float]), `tool_used` (enum: DocumentIntelligence/GPT4Vision), `completeness_score` (0-1), `raw_text` (optional)
   - Validation: Confidence scores 0-1, completeness 0-1, tool_used must match enum
   - Relationships: Belongs to LoanApplication (1:many)

3. **CreditReport**
   - Fields: `ssn`, `credit_score` (300-850), `payment_history`, `credit_utilization` (0-100), `accounts_open`, `derogatory_marks`, `credit_age_months`, `retrieved_at`
   - Validation: Credit score range, utilization percentage, non-negative counts
   - Source: Mock database via MCP

4. **RiskAssessment**
   - Fields: `application_id`, `dti_ratio`, `ltv_ratio`, `pti_ratio`, `risk_level` (enum: low/medium/high), `risk_factors` (list[str]), `mitigating_factors` (list[str]), `gpt4_reasoning`, `credit_score`, `timestamp`
   - Validation: Ratios as percentages, 3 risk factors, 3 mitigating factors minimum
   - Relationships: One per LoanApplication

5. **ComplianceReport**
   - Fields: `application_id`, `query`, `retrieved_policies` (list[PolicyChunk]), `compliance_status` (enum: compliant/non_compliant/needs_review), `cited_policies` (list[str]), `gpt4_analysis`, `timestamp`
   - Validation: At least 1 retrieved policy if compliant/non_compliant
   - Relationships: One per LoanApplication

6. **LendingDecision**
   - Fields: `application_id`, `decision_status` (enum: Approved/Rejected/Conditional/Pending), `interest_rate` (optional float), `conditions` (list[str]), `explanation`, `confidence_level` (0-1), `timestamp`
   - Validation: Interest rate present if Approved, conditions present if Conditional
   - Relationships: One per LoanApplication (final output)

7. **ApplicationState** (LangGraph)
   - Fields: `application_id`, `documents` (list[str]), `extracted_data` (dict), `risk_assessment` (RiskAssessment), `compliance_result` (ComplianceReport), `final_decision` (LendingDecision), `errors` (list[str]), `execution_metadata` (dict)
   - Validation: State progression rules, no skipped agents
   - Usage: Passed between LangGraph agents

8. **PolicyDocument** (RAG)
   - Fields: `doc_id`, `title`, `content`, `chunks` (list[PolicyChunk]), `embeddings` (list[list[float]]), `metadata` (dict)
   - PolicyChunk: `chunk_id`, `text`, `embedding`, `doc_id`, `start_idx`, `end_idx`
   - Validation: Chunks non-empty, embedding dimensions match (1536 for Ada-002)

**Deliverable**: `data-model.md` with complete Pydantic class definitions, validation rules, relationships

### 1.2 API Contract Generation (`contracts/mcp-server.yaml`)

Define MCP server OpenAPI specification:

**Endpoints**:

1. **GET /files/{filename}**
   - Description: Retrieve uploaded document from filesystem
   - Parameters: `filename` (path parameter, string)
   - Response 200: `{ "filename": str, "content": bytes (base64), "size": int, "mime_type": str }`
   - Response 404: `{ "error": "File not found" }`
   - Tags: FileAccess

2. **GET /credit/{ssn}**
   - Description: Query mock credit bureau database
   - Parameters: `ssn` (path parameter, string, format: XXX-XX-XXXX)
   - Response 200: `CreditReport` schema
   - Response 404: `{ "credit_score": null, "status": "no_history", "message": str }`
   - Tags: CreditBureau

3. **GET /application/{app_id}**
   - Description: Retrieve application metadata
   - Parameters: `app_id` (path parameter, string)
   - Response 200: `LoanApplication` schema (subset of fields)
   - Response 404: `{ "error": "Application not found" }`
   - Tags: ApplicationMetadata

4. **POST /admin/seed_credit_db**
   - Description: Populate mock credit database with test profiles (admin only)
   - Request body: None
   - Response 200: `{ "message": str, "records": int }`
   - Tags: Admin

5. **GET /health**
   - Description: Health check endpoint
   - Response 200: `{ "status": "healthy", "timestamp": str }`
   - Tags: System

**Deliverable**: `contracts/mcp-server.yaml` OpenAPI 3.0 specification with complete endpoint definitions

### 1.3 Quickstart Guide (`quickstart.md`)

Create setup and first-run instructions:

**Sections**:

1. **Prerequisites**
   - Python 3.10+ installation check
   - VS Code + Jupyter extension OR JupyterLab
   - Azure account with OpenAI, Document Intelligence, AI Search services
   - Git for cloning repo

2. **Environment Setup**
   - Clone repository
   - Copy `.env.example` to `.env`
   - Fill in Azure credentials:
     - `AZURE_OPENAI_API_KEY`
     - `AZURE_OPENAI_ENDPOINT`
     - `AZURE_OPENAI_DEPLOYMENT_NAME` (GPT-4)
     - `AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME` (Ada-002)
     - `AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`
     - `AZURE_DOCUMENT_INTELLIGENCE_KEY`
     - `AZURE_SEARCH_ENDPOINT`
     - `AZURE_SEARCH_KEY`
   - Install dependencies: `pip install -r requirements.txt`

3. **First Run - Setup Validation**
   - Open `notebooks/00_setup_and_test.ipynb`
   - Run all cells to validate Azure connections
   - Expected output: ✅ GPT-4 chat test, ✅ embeddings, ✅ Document Intelligence, ✅ AI Search
   - Troubleshooting: Common errors and fixes

4. **Seed Mock Data**
   - Run `python src/mcp/seed_data.py` to create mock credit database
   - Expected output: 4 test profiles created in `data/mock_credit_bureau.db`

5. **First Agent Run - Document Extraction**
   - Open `notebooks/01_document_agent.ipynb`
   - Upload sample pay stub from `tests/sample_applications/pay_stub_clean.pdf`
   - Run extraction cells
   - Expected output: JSON with extracted fields, confidence scores, completeness

6. **Start MCP Server (Optional)**
   - Terminal: `python src/mcp/server.py`
   - Server runs at `http://localhost:8000`
   - Test: `curl http://localhost:8000/credit/123-45-6789`

7. **Next Steps**
   - Proceed to `02_risk_agent.ipynb` for financial analysis
   - Follow notebook sequence for progressive learning

**Deliverable**: `quickstart.md` with step-by-step setup and validation instructions

### 1.4 Agent Context Update

Run `.specify/scripts/powershell/update-agent-context.ps1 -AgentType copilot` to update agent context with technology stack from this plan.

**Deliverables Summary (Phase 1)**:
- ✅ `data-model.md`: Complete Pydantic schemas
- ✅ `contracts/mcp-server.yaml`: OpenAPI specification
- ✅ `quickstart.md`: Setup and first-run guide
- ✅ Agent context updated with technology stack

---

## Phase 2: Task Breakdown

**Note**: Phase 2 (task creation) is executed via separate `/speckit.tasks` command. This plan provides the foundation for task generation.

**Task Organization Preview**:

**Epic 1: Document Processing Agent (P1)**
- Implement Azure Document Intelligence integration
- Implement GPT-4 Vision fallback logic
- Build field normalization with GPT-4 text
- Add validation rules engine
- Create completeness scoring
- Notebook 01 completion

**Epic 2: Risk Analysis Agent (P1)**
- Implement MCP server FastAPI app
- Build SQLite credit database connector
- Implement DTI/LTV/PTI calculations
- Integrate GPT-4 risk analysis prompts
- Create Plotly visualizations
- Notebook 02 completion

**Epic 3: RAG System (P2)**
- Set up Azure AI Search index
- Implement document chunking strategy
- Build Ada-002 embedding pipeline
- Create semantic search retriever
- Notebook 03 completion

**Epic 4: Compliance Agent (P2)**
- Integrate RAG retriever with compliance logic
- Build GPT-4 policy checking prompts
- Implement citation extraction
- Notebook 04 completion

**Epic 5: Decision Agent (P2)**
- Implement decision rules matrix
- Build GPT-4 decision analysis prompts
- Create rate calculation logic
- Implement explanation generation
- Notebook 05 completion

**Epic 6: Orchestration (P3)**
- Define LangGraph ApplicationState
- Implement agent nodes
- Build state transition edges
- Add error handling paths
- Notebook 06 completion

**Epic 7: MLflow Integration (P3)**
- Set up MLflow local server
- Implement logging for each agent
- Create artifact storage
- Build comparison utilities
- Notebook 07 completion

**Epic 8: Testing & Documentation**
- Write unit tests for calculations
- Create MCP server integration tests
- Document sample applications
- Update README with learnings

---

## Implementation Notes

**Development Workflow**:
1. Start with notebooks for rapid prototyping and learning
2. Extract reusable logic into `src/` modules as patterns emerge
3. Test modules with pytest while iterating in notebooks
4. Document discoveries and design decisions in notebook markdown cells

**Azure Service Setup Order**:
1. Azure OpenAI (GPT-4 + Ada-002 deployments) - Required first
2. Azure Document Intelligence (create resource) - For document agent
3. Azure AI Search (create service) - Before RAG implementation
4. MLflow (local install) - Last, after agents working

**Cost Management**:
- Use Document Intelligence free tier initially (first 500 pages/month free)
- Azure OpenAI: Track token usage via MLflow, set monthly budget alerts
- Azure AI Search: Free tier supports 50MB storage (sufficient for 5-10 policy docs)
- Estimated cost for 100 test applications: <$20 (mostly GPT-4 calls)

**Success Metrics**:
- All 7 notebooks runnable end-to-end without errors
- 90%+ Document Intelligence usage (10% Vision fallback)
- Complete workflow <60 seconds per application
- Learners complete all phases within 8 weeks per implementation guide

**Risks & Mitigations**:
- Risk: Azure service quotas for free/trial accounts
  - Mitigation: Document quota limits, provide upgrade guidance if needed
- Risk: GPT-4 response variability affecting test consistency
  - Mitigation: Use temperature=0 for deterministic outputs, retry logic
- Risk: Learner environment setup issues
  - Mitigation: Comprehensive quickstart.md, common error troubleshooting section

---

## Next Steps

1. **Complete Phase 0**: Execute research tasks, document decisions in `research.md`
2. **Complete Phase 1**: Create data-model.md, contracts/mcp-server.yaml, quickstart.md
3. **Run `/speckit.tasks`**: Break down epics into concrete implementation tasks
4. **Begin Implementation**: Start with Epic 1 (Document Agent) following task sequence
5. **Iterate**: Build notebook by notebook, test incrementally, document learnings

**Branch Status**: `001-ai-loan-underwriting-system` ready for implementation  
**Specification**: Complete and validated (see [checklists/requirements.md](./checklists/requirements.md))  
**Plan**: Ready for task breakdown via `/speckit.tasks`
