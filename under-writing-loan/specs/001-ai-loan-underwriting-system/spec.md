# Feature Specification: Multi-Agent AI Loan Underwriting System

**Feature Branch**: `001-ai-loan-underwriting-system`  
**Created**: November 19, 2025  
**Status**: Draft  
**Input**: Educational research project to learn AI agent orchestration, Gen AI reasoning, OCR, RAG, and MCP integration through building a loan underwriting system

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Document Processing & Extraction (Priority: P1)

A learner wants to understand how AI extracts structured data from unstructured loan application documents (pay stubs, bank statements, tax returns) using Azure Document Intelligence.

**Why this priority**: Foundation for all other agents - without document extraction, no downstream analysis is possible. This represents the entry point data pipeline and demonstrates cost-effective document processing strategies.

**Independent Test**: Upload a sample pay stub PDF, system extracts structured fields (employer name, gross/net income, pay period) as JSON with confidence scores using Document Intelligence.

**Acceptance Scenarios**:

1. **Given** a clean digital pay stub PDF, **When** learner uploads it via notebook, **Then** Azure Document Intelligence extracts all required fields with >0.7 confidence and returns structured JSON matching Pydantic schema
2. **Given** extracted data from Document Intelligence, **When** GPT-4o normalization runs, **Then** field names are unified and derived values (monthly from annual income) are calculated
3. **Given** normalized extraction results, **When** validation pass executes, **Then** system checks consistency rules (net <= gross income, dates chronological) and flags violations
4. **Given** completed extraction, **When** learner views output in notebook, **Then** see JSON with completeness score and confidence per field

---

### User Story 2 - Financial Risk Analysis (Priority: P1)

A learner wants to understand how AI agents calculate financial metrics (DTI, LTV, PTI) and perform risk assessment by combining structured rules with GPT-4 reasoning.

**Why this priority**: Core underwriting logic - demonstrates both deterministic calculation and AI-powered interpretation. Shows MCP data access pattern and how agents combine multiple data sources.

**Independent Test**: Given extracted document data and SSN, system queries mock credit database via MCP, calculates financial ratios, prompts GPT-4o for risk analysis, and returns risk level (low/medium/high) with reasoning.

**Acceptance Scenarios**:

1. **Given** extracted income/debt data and an SSN, **When** risk agent executes, **Then** MCP server queries mock credit database and returns credit score, payment history, utilization
2. **Given** extracted data and credit info, **When** financial calculations run, **Then** system computes DTI = (monthly debt / monthly income) × 100, LTV = (loan amount / property value) × 100, PTI accurately
3. **Given** calculated metrics, **When** GPT-4o risk analysis prompt executes, **Then** LLM returns risk level with top 3 risk factors and top 3 mitigating factors
4. **Given** completed risk assessment, **When** learner views results in notebook, **Then** see interactive Plotly chart of DTI/LTV/PTI bars and GPT-4's step-by-step reasoning
5. **Given** multiple test profiles (excellent 820 score vs risky 620 score), **When** learner processes both, **Then** system produces different risk levels and reasoning reflecting credit quality differences

---

### User Story 3 - Policy Compliance via RAG (Priority: P2)

A learner wants to understand how Retrieval Augmented Generation (RAG) improves AI accuracy by retrieving relevant lending policies and using them as context for compliance checking.

**Why this priority**: Demonstrates semantic search and context augmentation - key technique for grounding LLM responses in specific organizational knowledge. Critical for understanding vector embeddings.

**Independent Test**: Given a compliance question ("Is DTI 38% acceptable?"), system embeds query, searches Azure AI Search for relevant policy chunks, retrieves top-k results, passes to GPT-4 with context, and returns grounded answer citing specific policy.

**Acceptance Scenarios**:

1. **Given** 5-10 lending policy documents, **When** offline indexing runs, **Then** system chunks documents, generates Ada-002 embeddings, and stores in Azure AI Search with metadata
2. **Given** indexed policies and a natural language query, **When** learner submits question in notebook, **Then** system embeds query using same model and performs cosine similarity search
3. **Given** search results, **When** top 3 chunks retrieved, **Then** system constructs context string and sends to GPT-4 with compliance checking prompt
4. **Given** GPT-4 response with context, **When** learner compares to response without RAG, **Then** context-augmented answer cites specific policy section and is more accurate
5. **Given** edge case query not in policies, **When** RAG search returns low similarity scores, **Then** system acknowledges lack of relevant policy and avoids hallucination

---

### User Story 4 - Final Decision & Explanation Generation (Priority: P2)

A learner wants to understand how AI makes transparent lending decisions by aggregating outputs from all previous agents and generating human-readable explanations.

**Why this priority**: Demonstrates multi-factor AI reasoning and explainability - critical for trustworthy AI systems. Shows how to combine rules-based logic with LLM judgment.

**Independent Test**: Given outputs from document, risk, and compliance agents, decision agent applies rules matrix, prompts GPT-4 for comprehensive analysis, calculates risk-adjusted interest rate, and returns decision (Approved/Rejected/Conditional) with detailed explanation.

**Acceptance Scenarios**:

1. **Given** complete agent outputs (extracted data, risk assessment, compliance report), **When** decision agent aggregates, **Then** system combines all factors into single state object
2. **Given** aggregated state, **When** decision rules execute, **Then** system applies thresholds (e.g., auto-reject if DTI >43% and credit <640) deterministically
3. **Given** borderline case not matching clear rules, **When** GPT-4 decision prompt executes, **Then** LLM provides recommendation balancing all factors with transparent reasoning
4. **Given** approved decision, **When** rate calculation runs, **Then** system computes risk-adjusted interest rate based on credit score and risk level
5. **Given** final decision, **When** explanation generation prompt executes, **Then** GPT-4 produces plain-language summary explaining key approval/rejection factors and any conditions

---

### User Story 5 - Multi-Agent Orchestration with LangGraph (Priority: P3)

A learner wants to understand how LangGraph coordinates sequential agent execution, manages state persistence across agents, and handles error scenarios in multi-agent workflows.

**Why this priority**: Advanced orchestration pattern - builds on all previous stories. Demonstrates production-ready workflow management but not strictly required for learning individual agent concepts.

**Independent Test**: Submit complete loan application, LangGraph executes document → risk → compliance → decision agents in sequence, persists state between transitions, handles agent failures gracefully, and returns final output with execution metadata.

**Acceptance Scenarios**:

1. **Given** a complete loan application (PDFs + applicant info), **When** orchestrator invokes workflow, **Then** LangGraph initializes ApplicationState and executes document agent first
2. **Given** document agent completes successfully, **When** state transition occurs, **Then** extracted_data populates ApplicationState and risk agent receives it as input
3. **Given** risk agent completes, **When** compliance agent executes, **Then** ApplicationState contains both extracted_data and risk_assessment for policy checking
4. **Given** document agent fails with OCR error, **When** error handler triggers, **Then** workflow transitions to Error state with descriptive message and does not execute downstream agents
5. **Given** complete workflow execution, **When** learner views orchestration notebook, **Then** see state evolution across agents, execution time per agent, and final decision with full audit trail

---

### User Story 6 - Experiment Tracking with MLflow (Priority: P3)

A learner wants to understand how to track ML experiments by logging agent execution metrics, comparing different prompts/models, and visualizing performance over multiple test cases.

**Why this priority**: Best practice for ML reproducibility - valuable but not critical for understanding core agent logic. Most useful after multiple experiments to compare variations.

**Independent Test**: Process 10+ diverse loan applications, MLflow logs execution time, token usage, costs per agent, approval rate, and prompt versions, then learner views dashboard comparing experiments.

**Acceptance Scenarios**:

1. **Given** MLflow local server running, **When** orchestrator processes application, **Then** system logs start time, end time, parameters (model name, temperature), and metrics (tokens, cost) per agent
2. **Given** multiple applications processed, **When** learner opens MLflow UI, **Then** see run history with approval rate, average processing time, and cost per application
3. **Given** two different risk analysis prompts, **When** learner runs same test cases with both, **Then** MLflow tracks as separate experiments and enables side-by-side comparison
4. **Given** logged artifacts, **When** learner inspects specific run, **Then** see saved outputs (extracted JSONs, risk assessments, decisions) for reproducibility
5. **Given** 20+ applications across multiple experiments, **When** learner queries MLflow, **Then** can filter by parameters (e.g., all runs with GPT-4 vs GPT-3.5) and compare performance metrics

---

### User Story 7 - Cost Optimization & Tracking (Priority: P3)

A learner wants to understand cost tracking and optimization by monitoring Document Intelligence usage and analyzing extraction patterns.

**Why this priority**: Real-world production concern - demonstrates practical AI engineering beyond pure functionality. Teaches budget-conscious development.

**Independent Test**: Process batch of documents, system tracks Document Intelligence costs, logs confidence scores, and reports cost breakdown per document.

**Acceptance Scenarios**:

1. **Given** a batch of 10 digital PDFs, **When** document agent processes, **Then** system logs Document Intelligence cost (~$0.001/page) for each document
2. **Given** extraction results, **When** Document Intelligence returns varying confidence scores, **Then** system logs confidence levels and extraction quality metrics
3. **Given** completed batch processing, **When** learner views cost analysis, **Then** see per-document cost breakdown and recommendations for cost optimization
4. **Given** logged extraction patterns, **When** learner analyzes quality, **Then** identify document types with low confidence as candidates for improved preprocessing
5. **Given** cost tracking over time, **When** learner reviews cumulative metrics, **Then** understand total Document Intelligence expenses and usage patterns

---

### Edge Cases

- **What happens when** uploaded PDF is corrupted or unreadable by Document Intelligence?
  - System logs error, marks document as "manual_review_required", does not block other documents in batch, and continues workflow with partial data flagged
  
- **What happens when** MCP server is unreachable during credit lookup?
  - Risk agent retries 3 times with exponential backoff, if still failing returns risk assessment with "credit_score: null" and higher risk level due to missing data, logs connectivity issue

- **What happens when** Azure AI Search returns zero relevant policy results for compliance query?
  - Compliance agent acknowledges no applicable policy found, prompts GPT-4 to state "insufficient policy guidance" rather than hallucinate, marks application as "pending_manual_review"

- **What happens when** two agents return contradictory information (e.g., extracted income differs between document types)?
  - Decision agent flags discrepancy in explanation, prompts GPT-4 to highlight inconsistency, recommends "conditional_approval pending income verification"

- **What happens when** learner runs notebook without Azure credentials configured?
  - Setup validation cell fails immediately with clear error message pointing to .env.example, prevents cryptic API errors downstream

- **What happens when** GPT-4 returns malformed JSON instead of expected Pydantic schema?
  - Validation layer catches Pydantic parsing error, logs raw response, retries with explicit schema instruction in prompt (max 3 retries), then fails gracefully with error message

- **How does system handle** extremely high loan amounts exceeding typical policy ranges?
  - Compliance agent retrieves policies, GPT-4 identifies amount as outlier, decision agent automatically flags as "requires_senior_review" regardless of other factors

- **How does system handle** missing critical document types (e.g., no pay stub uploaded)?
  - Document agent returns extraction result with completeness score <0.5, downstream agents receive partial data, decision agent returns "pending_additional_documents" status listing missing items

## Requirements *(mandatory)*

### Functional Requirements

**Document Processing**

- **FR-001**: System MUST accept PDF uploads for pay stubs, bank statements, tax returns, and identification documents via notebook interface
- **FR-002**: System MUST use Azure Document Intelligence extraction using appropriate prebuilt models (pay stub, invoice, ID document models)
- **FR-003**: System MUST normalize extracted field names and infer derived values (monthly income from annual) using GPT-4o text mode
- **FR-004**: System MUST validate extracted data against consistency rules (net <= gross income, dates chronological, non-negative balances)
- **FR-005**: System MUST return structured JSON output matching Pydantic schema with completeness score and confidence metrics per field
- **FR-006**: System MUST log extraction results with confidence scores for quality analysis

**Financial Risk Analysis**

- **FR-007**: System MUST query mock credit database via MCP server using applicant SSN to retrieve credit score, payment history, utilization, accounts, derogatory marks, credit age
- **FR-008**: System MUST calculate DTI ratio as (total monthly debt / gross monthly income) × 100
- **FR-009**: System MUST calculate LTV ratio as (loan amount / property value) × 100
- **FR-010**: System MUST calculate PTI ratio as (monthly loan payment / gross monthly income) × 100 using standard amortization formula
- **FR-011**: System MUST prompt GPT-4o with calculated metrics and credit data to generate risk level (low/medium/high) with reasoning
- **FR-012**: System MUST identify top 3 risk factors and top 3 mitigating factors in risk assessment
- **FR-013**: System MUST visualize financial metrics (DTI, LTV, PTI) using Plotly interactive charts in notebook output

**Policy Compliance (RAG)**

- **FR-014**: System MUST index lending policy documents by chunking text (500 token chunks), generating Ada-002 embeddings, and storing in Azure AI Search
- **FR-015**: System MUST embed compliance queries using same Ada-002 model and perform cosine similarity search against indexed policies
- **FR-016**: System MUST retrieve top 3 most relevant policy chunks and include as context in GPT-4o compliance checking prompt
- **FR-017**: System MUST return compliance report citing specific policy sections when available
- **FR-018**: System MUST acknowledge when no relevant policy found (low similarity scores) and avoid hallucinating policy requirements

**Decision Making**

- **FR-019**: System MUST aggregate outputs from document, risk, and compliance agents into unified ApplicationState object
- **FR-020**: System MUST apply deterministic decision rules (e.g., auto-reject if DTI >43% AND credit_score <640)
- **FR-021**: System MUST prompt GPT-4o for comprehensive decision analysis on borderline cases not matching clear rules
- **FR-022**: System MUST calculate risk-adjusted interest rate based on credit score tiers and risk level
- **FR-023**: System MUST return decision status (Approved, Rejected, Conditional, Pending) with confidence level
- **FR-024**: System MUST generate plain-language explanation of decision factors using GPT-4o, highlighting key approval/rejection reasons

**Multi-Agent Orchestration**

- **FR-025**: System MUST use LangGraph to define stateful workflow: Init → DocumentAgent → RiskAgent → ComplianceAgent → DecisionAgent → Complete
- **FR-026**: System MUST persist ApplicationState across agent transitions, ensuring each agent receives outputs from previous agents
- **FR-027**: System MUST implement error handling paths that transition to Error state on agent failure without executing downstream agents
- **FR-028**: System MUST log execution time and output size per agent for performance monitoring

**MCP Server & Data Access**

- **FR-029**: System MUST implement FastAPI MCP server with three connectors: file storage (read PDFs), credit database (query SQLite), application metadata (query SQLite)
- **FR-031**: System MUST provide `/files/{filename}` endpoint returning document bytes from local filesystem
- **FR-032**: System MUST provide `/credit/{ssn}` endpoint querying mock_credit_bureau.db and returning credit report
- **FR-033**: System MUST provide `/application/{app_id}` endpoint querying database.sqlite for application metadata
- **FR-034**: System MUST implement database seeding endpoint `/admin/seed_credit_db` to populate mock credit profiles
- **FR-035**: System MUST return consistent JSON response format across all MCP endpoints with appropriate HTTP status codes

**Experiment Tracking**

- **FR-036**: System MUST log to MLflow local server for each application: execution time, token count, cost estimate, agent parameters (model, temperature), decision outcome
- **FR-037**: System MUST save agent outputs (extracted JSON, risk assessment, compliance report, decision) as MLflow artifacts for reproducibility
- **FR-038**: System MUST support experiment comparison by logging prompt versions and model names as parameters

**Development Experience**

- **FR-039**: System MUST provide Jupyter notebooks as primary interface for each phase (setup, document, risk, RAG, compliance, decision, orchestration, MLflow)
- **FR-040**: System MUST include interactive visualizations (Plotly charts, expandable JSON viewers) in notebook outputs
- **FR-041**: System MUST validate Azure credentials on setup and provide clear error messages pointing to .env configuration if missing
- **FR-042**: System MUST include sample test data (4+ mock credit profiles, 5+ sample documents, 5+ policy documents) for immediate experimentation

### Key Entities *(include if feature involves data)*

- **LoanApplication**: Represents a complete loan request with applicant_id, loan_amount, property_value, uploaded_documents (list of PDF paths), created_at, status
- **ExtractedDocument**: Structured data from a single document with document_type (pay_stub/bank_statement/tax_return/id), extracted_fields (dict), confidence_scores (per field), tool_used (DocumentIntelligence/GPT4Vision), completeness_score (0-1)
- **CreditReport**: Mock credit bureau data with ssn, credit_score (300-850), payment_history (percentage on-time), credit_utilization (percentage), accounts_open (count), derogatory_marks (count), credit_age_months
- **RiskAssessment**: Financial analysis output with dti_ratio (percentage), ltv_ratio (percentage), pti_ratio (percentage), risk_level (low/medium/high), risk_factors (list of strings), mitigating_factors (list of strings), gpt4_reasoning (text)
- **ComplianceReport**: Policy check results with query (original question), retrieved_policies (list of relevant chunks), compliance_status (compliant/non_compliant/needs_review), cited_policies (list of policy sections), gpt4_analysis (text)
- **LendingDecision**: Final decision with application_id, decision_status (Approved/Rejected/Conditional/Pending), interest_rate (percentage or null), conditions (list of requirements), explanation (plain-language reasoning), confidence_level (0-1), timestamp
- **ApplicationState**: LangGraph state object containing application_id, documents (list), extracted_data (dict), risk_assessment (RiskAssessment), compliance_result (ComplianceReport), final_decision (LendingDecision), errors (list of error messages), execution_metadata (timing per agent)
- **PolicyDocument**: RAG indexed document with doc_id, title, content (original text), chunks (list of text segments), embeddings (list of vectors), metadata (source, date, category)

## Success Criteria *(mandatory)*

### Measurable Outcomes

**Learning Outcomes (Primary Goal)**

- **SC-001**: Learners can successfully process a loan application end-to-end (upload documents → receive decision) within 30 minutes in their first session, demonstrating all 4 agents working together
- **SC-002**: Learners understand document extraction cost optimization - can explain Document Intelligence usage patterns and cost per document
- **SC-003**: Learners can articulate how RAG improves accuracy - demonstrate by comparing GPT-4o responses with vs without policy context showing measurable increase in factual correctness
- **SC-004**: Learners successfully modify agent prompts and observe different outcomes - change risk analysis prompt and see altered reasoning in 2+ test cases
- **SC-005**: Learners complete all 7 notebook phases within 8 weeks following implementation guide, with each notebook building working components

**System Performance**

- **SC-006**: Document extraction completes in under 10 seconds per document for standard clean PDFs using Document Intelligence
- **SC-007**: System processes standard documents (pay stubs, bank statements from major institutions) reliably using Document Intelligence
- **SC-008**: RAG semantic search retrieves at least 1 relevant policy chunk with >0.7 similarity score for 95% of compliance queries covered in indexed policies
- **SC-009**: Complete multi-agent workflow (all 4 agents) processes a single application in under 60 seconds excluding document upload time
- **SC-010**: System handles 10+ test applications in single notebook session without manual intervention or runtime errors

**Data Quality & Accuracy**

- **SC-011**: Document extraction achieves 95%+ field accuracy on test dataset of 20+ clean sample documents compared to manually labeled ground truth
- **SC-012**: Financial calculations (DTI, LTV, PTI) are mathematically correct within 0.1% tolerance on 100% of test cases
- **SC-013**: GPT-4o risk reasoning includes all required sections (risk level, 3 risk factors, 3 mitigating factors) in 95%+ of assessments
- **SC-014**: Compliance reports cite actual policy text (not hallucinated) in 90%+ of cases when relevant policies exist in index

**Experiment Reproducibility**

- **SC-015**: MLflow successfully logs metrics for 100% of completed application workflows without crashes or missing data
- **SC-016**: Saved MLflow artifacts allow learners to reproduce exact agent outputs from previous runs by loading parameters and inputs
- **SC-017**: Learners can compare 2+ prompt variations side-by-side in MLflow UI and identify performance differences

**Developer Experience**

- **SC-015**: Setup notebook completes all Azure connection tests (GPT-4o, embeddings, Document Intelligence, AI Search) in under 5 minutes with valid credentials
- **SC-016**: Error messages provide actionable guidance - 90%+ of configuration errors include specific fix instructions (e.g., "Set AZURE_OPENAI_ENDPOINT in .env")
- **SC-017**: Notebook visualizations (Plotly charts, JSON viewers) render correctly in JupyterLab and VS Code notebook interface
- **SC-018**: Sample test data enables learners to run every notebook without needing to source external documents

**Cost Efficiency (Research Budget)**

- **SC-019**: Processing 100 sample applications costs ~$12-18 using Document Intelligence extraction and GPT-4o reasoning
- **SC-020**: System logs per-application cost breakdown enabling learners to project scaling costs accurately
