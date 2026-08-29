# Research & Technology Decisions

**Feature**: Multi-Agent AI Loan Underwriting System  
**Date**: November 19, 2025  
**Status**: Complete

## Overview

This document captures technology research, decisions, and rationale for building an educational multi-agent AI system. All decisions prioritize learning value and cost-effectiveness for research use.

---

## 1. Azure Document Intelligence Prebuilt Models

**Research Question**: Which prebuilt models support our document types (pay stubs, bank statements, tax returns, IDs)?

### Investigation

Azure Document Intelligence (formerly Form Recognizer) offers several prebuilt models:

| Document Type | Recommended Model | Key Fields Extracted | Confidence |
|---------------|-------------------|---------------------|------------|
| Pay Stubs | **Prebuilt Invoice** (best fit) | Employer name, gross/net pay, pay period, deductions, YTD totals | High (0.8-0.95) for standard layouts |
| Bank Statements | **Prebuilt Invoice** | Account holder, account number, balance, transactions (table), dates | Medium-High (0.7-0.9) |
| Tax Returns (W-2) | **Prebuilt Tax (US)** - W-2 model | Employer EIN, employee SSN, wages, withholding | Very High (0.9+) |
| Driver's License | **Prebuilt ID Document** | Name, DOB, license number, address, expiration | Very High (0.9+) |
| Employment Letters | **Prebuilt Read** (OCR only) + GPT-4 extraction | No structured extraction - use as text source | N/A |

**Azure Documentation**:
- Invoice model: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-invoice
- ID document model: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-id-document
- Tax document models: https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept-tax-document

### Decision

**Primary Strategy**:
1. **Pay stubs → Invoice model**: Best match for structured financial documents with line items
2. **Bank statements → Invoice model**: Handles tables and summary sections well
3. **Tax returns → Tax W-2 model**: Purpose-built for US tax forms
4. **IDs → ID Document model**: Specialized for driver's licenses, passports
5. **Custom documents → Read model + GPT-4 text**: Extract text then structured extraction via LLM

**No Vision Fallback**: System uses Document Intelligence only, with GPT-4 text mode for normalization

**Rationale**:
- Invoice model versatile for financial documents despite "pay stub" not being explicit use case
- Purpose-built models (Tax, ID) have highest accuracy - use when available
- Read model provides clean text for GPT-4 text mode when structure doesn't fit prebuilt models
- Document Intelligence provides structured extraction with confidence scores for quality assessment
- GPT-4 text mode handles field normalization and validation (separate from extraction)

**Alternatives Considered**:
- ❌ **Custom model training**: Requires labeled dataset (200+ documents), adds complexity, doesn't teach prebuilt model usage
- ❌ **GPT-4 Vision for extraction**: 10-20x more expensive, unnecessary for digital PDFs with Document Intelligence
- ❌ **Open-source OCR (Tesseract)**: Lower quality, no structured extraction, doesn't demonstrate Azure ecosystem

---

## 2. Document Intelligence Cost Analysis

**Research Question**: Cost model and processing expectations for educational use?

### Cost Analysis (as of Nov 2025)

| Service | Pricing Model | Cost per Document | Processing Speed | Usage |
|---------|---------------|-------------------|------------------|-------|
| **Document Intelligence** | Per page analyzed | ~$0.001-0.0015 per page (prebuilt models) | 2-5 seconds | All document extraction |
| **GPT-4o Text (normalization)** | Per token | ~$0.0001 per 1K tokens | 1-2 seconds | Field name unification, validation, derived calculations |

**Free Tier Allowances**:
- Document Intelligence: 500 pages/month free (first month), then pay-as-you-go
- Azure OpenAI: No free tier - pay per token from day 1

**100 Application Processing Estimate** (avg 2 pages per application):
- Document Intelligence: 200 pages × $0.0015 = **$0.30**
- GPT-4o text normalization: 100 applications × $0.005 = **$0.50**
- **Total: ~$0.80 for 100 applications**

### Decision

**Extraction Strategy**:
1. **Primary**: Azure Document Intelligence for all document extraction
2. **Normalization**: GPT-4o text mode for field standardization and derived calculations
3. **No Vision fallback**: Not needed for digital PDFs with Document Intelligence

**Confidence Handling**:
- Log confidence scores for quality analysis
- Flag low-confidence extractions (<0.7) for manual review
- Use confidence metrics to identify document types needing preprocessing

**Cost Tracking**:
- Track per-document Document Intelligence cost
- Log GPT-4o token usage for normalization
- Record extraction quality metrics for cost/quality analysis

**Alternatives Considered**:
- ❌ **GPT-4 Vision primary**: 20x more expensive ($0.01-0.03 per page), unnecessary for digital PDFs
- ❌ **No confidence tracking**: Misses opportunity to analyze extraction quality patterns
- ❌ **Manual extraction**: Defeats purpose of automation, not scalable

---

## 3. LangGraph State Management Patterns

**Research Question**: Best practices for ApplicationState design, error handling, agent communication?

### LangGraph Architecture Research

**State Design Pattern** (from LangGraph docs):
```python
from typing import TypedDict, List, Optional
from langgraph.graph import StateGraph

class ApplicationState(TypedDict):
    # Identity
    application_id: str
    
    # Inputs
    documents: List[str]  # File paths
    applicant_info: dict
    
    # Agent Outputs (accumulated)
    extracted_data: Optional[dict]
    risk_assessment: Optional[dict]
    compliance_result: Optional[dict]
    final_decision: Optional[dict]
    
    # Metadata
    errors: List[str]
    current_agent: str
    execution_times: dict[str, float]
```

**Agent Node Pattern**:
```python
def document_agent(state: ApplicationState) -> ApplicationState:
    """Agent returns updated state dict."""
    try:
        result = process_documents(state["documents"])
        return {
            **state,
            "extracted_data": result,
            "current_agent": "risk_agent"
        }
    except Exception as e:
        return {
            **state,
            "errors": state["errors"] + [str(e)],
            "current_agent": "error_handler"
        }
```

**Error Handling Pattern**:
```python
workflow = StateGraph(ApplicationState)

# Normal flow
workflow.add_node("document_agent", document_agent)
workflow.add_node("risk_agent", risk_agent)
workflow.add_edge("document_agent", "risk_agent")

# Error paths
workflow.add_conditional_edges(
    "document_agent",
    lambda state: "error_handler" if state.get("errors") else "risk_agent"
)
```

### Decision

**State Schema**:
- **Flat dict with optional fields**: Simplest for educational use, easy to debug
- **Type hints for clarity**: TypedDict provides IDE support without runtime overhead
- **Accumulative pattern**: Each agent adds to state, never removes (audit trail)
- **Error list**: Collect all errors, don't stop on first failure (helps debugging)

**Agent Communication**:
- **State is single source of truth**: Agents read inputs from state, write outputs to state
- **No direct agent-to-agent calls**: All communication via LangGraph state transitions
- **Conditional edges for branching**: Use lambdas to route based on state conditions

**Error Handling**:
- **Graceful degradation**: Agents return partial results + error if possible
- **Error state node**: Central error handler that logs and decides next action
- **No exceptions escape agents**: Catch all, return in state.errors list

**Execution Metadata**:
- Track timing per agent in `execution_times` dict
- Log state size for performance monitoring
- Record which agent set which field (attribution)

**Rationale**:
- LangGraph manages state persistence automatically - we just return updated dicts
- Conditional edges enable smart routing (skip agents if prerequisites missing)
- Error list pattern prevents workflow halt on single agent failure
- TypedDict provides type safety for learners without runtime Pydantic overhead in graph

**Alternatives Considered**:
- ❌ **Pydantic for ApplicationState**: LangGraph prefers simple dicts, Pydantic adds serialization overhead
- ❌ **Agent classes with shared state object**: More complex, hides LangGraph's functional pattern
- ❌ **Stop workflow on first error**: Poor for debugging, learners wouldn't see how far they got
- ❌ **Pass outputs as function args**: Doesn't leverage LangGraph state management benefits

**Reference**: https://langchain-ai.github.io/langgraph/tutorials/introduction/

---

## 4. Azure AI Search Free Tier Limitations

**Research Question**: Sufficient for 5-10 policy docs? Query throughput? Hybrid search support?

### Free Tier Specifications (Nov 2025)

| Feature | Free Tier Limit | Sufficient for Project? |
|---------|----------------|-------------------------|
| **Storage** | 50 MB | ✅ Yes (5-10 PDFs ~5-10MB) |
| **Documents** | 10,000 documents | ✅ Yes (policy chunks ~500-1000) |
| **Indexes** | 3 indexes | ✅ Yes (need 1: "lending-policies") |
| **Indexers/Data Sources** | 3 each | ✅ Yes (manual upload, no indexers needed) |
| **Query Throughput** | 3 queries/second | ✅ Yes (single learner, <1 QPS) |
| **Vector Search** | ✅ Supported | ✅ Yes (1536 dimensions for Ada-002) |
| **Hybrid Search** | ✅ Supported (semantic + keyword) | ✅ Yes (use for best recall) |
| **High Availability** | ❌ Not guaranteed | ⚠️ Acceptable (educational use, not production) |
| **SLA** | ❌ No SLA | ⚠️ Acceptable (no uptime requirements) |

**Azure AI Search Documentation**:
- Free tier: https://azure.microsoft.com/en-us/pricing/details/search/
- Vector search: https://learn.microsoft.com/en-us/azure/search/vector-search-overview
- Hybrid search: https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview

### Decision

**Configuration**:
- **Tier**: Free (F0) - sufficient for educational use
- **Index name**: `lending-policies-index`
- **Vector dimensions**: 1536 (Ada-002 standard)
- **Search type**: **Hybrid (vector + keyword)** for best results
- **Chunking strategy**: 500 tokens per chunk with 50 token overlap
- **Top K retrieval**: 3 chunks per query (balances context vs token cost)

**Index Schema**:
```json
{
  "fields": [
    {"name": "chunk_id", "type": "Edm.String", "key": true},
    {"name": "content", "type": "Edm.String", "searchable": true},
    {"name": "embedding", "type": "Collection(Edm.Single)", "dimensions": 1536, "vectorSearchProfile": "vector-profile"},
    {"name": "doc_title", "type": "Edm.String", "filterable": true},
    {"name": "doc_category", "type": "Edm.String", "filterable": true},
    {"name": "chunk_index", "type": "Edm.Int32", "sortable": true}
  ]
}
```

**Chunking Strategy Rationale**:
- 500 tokens ≈ 375 words ≈ 2-3 policy paragraphs (good semantic unit)
- 50 token overlap prevents splitting mid-requirement
- Preserves context across chunks for retrieval accuracy

**Hybrid Search Rationale**:
- **Vector search**: Captures semantic meaning ("maximum debt ratio" matches "DTI limit")
- **Keyword search**: Ensures exact term matches ("640 credit score" retrieves exact number)
- **Combined**: Best of both worlds - semantic understanding + precision

**Upgrade Path (if needed)**:
- If >50MB needed: Upgrade to Basic (B) tier ($75/month, 2GB storage)
- If production deployment: Upgrade to Standard (S1) tier for SLA + scaling

**Alternatives Considered**:
- ❌ **Local vector DB (Chroma, FAISS)**: Doesn't teach Azure ecosystem, no hybrid search out-of-box
- ❌ **Vector-only search**: Misses exact matches, lower precision on numeric queries
- ❌ **Keyword-only search**: Misses semantic similarity, poor recall on paraphrased queries
- ❌ **Larger chunks (1000 tokens)**: Dilutes semantic focus, more tokens to embed/retrieve

**Reference**: https://learn.microsoft.com/en-us/azure/search/search-create-service-portal

---

## 5. MLflow Local Setup for Educational Use

**Research Question**: Tracking server setup, artifact storage, experiment comparison UI?

### MLflow Architecture for Local Use

**Components**:
1. **Tracking Server**: SQLite backend, local filesystem artifact store
2. **Python Client**: Import in notebooks, log metrics/parameters/artifacts
3. **UI**: Built-in web interface at http://localhost:5000

**Setup Steps**:
```bash
# Install
pip install mlflow

# Start tracking server (terminal)
mlflow server --backend-store-uri sqlite:///data/mlflow.db \
              --default-artifact-root ./data/mlflow-artifacts \
              --host 127.0.0.1 \
              --port 5000
```

**Notebook Integration**:
```python
import mlflow

# Set tracking URI (in notebook)
mlflow.set_tracking_uri("http://127.0.0.1:5000")
mlflow.set_experiment("loan-underwriting")

# Log run
with mlflow.start_run(run_name="test-application-001"):
    # Log parameters
    mlflow.log_param("model", "gpt-4")
    mlflow.log_param("temperature", 0.0)
    
    # Log metrics
    mlflow.log_metric("extraction_time_seconds", 8.5)
    mlflow.log_metric("dti_ratio", 38.5)
    mlflow.log_metric("total_cost_usd", 0.05)
    
    # Log artifacts
    mlflow.log_artifact("data/extracted/app-001.json")
    mlflow.log_text(risk_assessment.reasoning, "risk_reasoning.txt")
```

### Decision

**Configuration**:
- **Backend store**: SQLite (`data/mlflow.db`) - zero config, sufficient for single user
- **Artifact store**: Local filesystem (`data/mlflow-artifacts/`) - simple, no cloud dependencies
- **Tracking URI**: `http://127.0.0.1:5000` - standard port, learners can bookmark
- **Experiment naming**: `loan-underwriting` (single experiment, runs per application)

**Logging Strategy**:
```python
# Per application run, log:
Parameters:
  - model_name: "gpt-4"
  - temperature: 0.0
  - document_intelligence_model: "prebuilt-invoice"
  - prompt_version: "v1.2"

Metrics:
  - document_extraction_time_s
  - risk_analysis_time_s
  - compliance_check_time_s
  - decision_generation_time_s
  - total_workflow_time_s
  - total_tokens_used
  - total_cost_usd
  - dti_ratio
  - ltv_ratio
  - credit_score

Artifacts:
  - extracted_data.json
  - risk_assessment.json
  - compliance_report.json
  - final_decision.json
  - full_application_state.json
```

**Experiment Comparison Use Cases**:
1. **Prompt engineering**: Compare v1 vs v2 risk analysis prompts on same test set
2. **Model comparison**: GPT-4 vs GPT-3.5-turbo for cost/quality tradeoffs
3. **Threshold tuning**: Different Document Intelligence confidence thresholds
4. **Performance tracking**: See if workflow speeds up over time with optimization

**UI Features**:
- Compare runs side-by-side (metrics table)
- Plot metrics across runs (scatter, line charts)
- Download artifacts from any run
- Filter/search runs by parameters
- Share run URLs with instructors/peers

**Rationale**:
- SQLite sufficient for 100s of runs (educational scale)
- Local artifacts keep PII data on learner's machine (no cloud exposure)
- Standard MLflow UI requires no custom dashboard development
- Logging patterns teach production ML ops practices

**Alternatives Considered**:
- ❌ **Cloud MLflow (Databricks)**: Overkill for educational use, costs money, setup complexity
- ❌ **Custom logging to CSV**: Reinvents wheel, no comparison UI, doesn't teach industry tools
- ❌ **No tracking**: Learners can't compare experiments, misses key learning objective
- ❌ **PostgreSQL backend**: Requires database setup, SQLite sufficient for scale

**Reference**: https://mlflow.org/docs/latest/getting-started/intro-quickstart/index.html

---

## 6. Pydantic v2 Best Practices for LLM Outputs

**Research Question**: JSON mode vs function calling? Retry strategies? Validation patterns?

### OpenAI API Options for Structured Output

| Approach | Pros | Cons | Reliability |
|----------|------|------|-------------|
| **JSON Mode** (`response_format={"type": "json_object"}`) | Simple, works with any prompt | Must parse JSON manually, validate with Pydantic after | Medium (GPT-4: ~95% valid JSON) |
| **Function Calling** (tools parameter) | OpenAI validates schema, direct JSON | More complex API, limited to function-like structures | High (GPT-4: ~98% valid) |
| **Structured Outputs** (new: `response_format={"type": "json_schema"}`) | Guaranteed valid JSON matching schema | Newer feature, slightly slower, requires schema | Very High (~99.9% valid) |

**Azure OpenAI Support** (as of Nov 2025):
- ✅ JSON Mode: Supported
- ✅ Function Calling: Supported
- ⚠️ Structured Outputs: **Not yet available** on Azure (OpenAI.com only)

### Decision

**Primary Approach**: **JSON Mode + Pydantic Validation + Retry**

```python
from pydantic import BaseModel, ValidationError
from openai import AzureOpenAI

class ExtractedPayStub(BaseModel):
    employer_name: str
    gross_income: float
    net_income: float
    pay_period_start: str  # ISO date
    pay_period_end: str

def extract_with_retry(client, prompt, model_class, max_retries=3):
    """Extract structured data with automatic retry on validation failure."""
    for attempt in range(max_retries):
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a data extraction assistant. Always respond with valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0  # Deterministic
        )
        
        try:
            json_data = json.loads(response.choices[0].message.content)
            validated = model_class.model_validate(json_data)
            return validated
        except (json.JSONDecodeError, ValidationError) as e:
            if attempt == max_retries - 1:
                raise Exception(f"Failed after {max_retries} attempts: {e}")
            # Log and retry with error feedback
            prompt += f"\n\nPrevious attempt failed: {e}. Please fix and return valid JSON."
    
    raise Exception("Extraction failed")
```

**Prompt Engineering Pattern**:
```python
prompt = f"""
Extract structured data from this pay stub.

Required fields:
- employer_name (string)
- gross_income (number, dollars)
- net_income (number, dollars)
- pay_period_start (ISO date: YYYY-MM-DD)
- pay_period_end (ISO date: YYYY-MM-DD)

Pay stub text:
{ocr_text}

Return JSON matching this exact schema:
{{
  "employer_name": "string",
  "gross_income": 0.0,
  "net_income": 0.0,
  "pay_period_start": "YYYY-MM-DD",
  "pay_period_end": "YYYY-MM-DD"
}}
"""
```

**Validation Strategy**:
1. **Schema validation**: Pydantic catches missing fields, wrong types
2. **Business logic validation**: Custom validators for:
   - `net_income <= gross_income`
   - `pay_period_end > pay_period_start`
   - `gross_income > 0`
3. **Retry with feedback**: If validation fails, include error in next prompt

**Rationale**:
- JSON mode + Pydantic gives learners control and visibility into process
- Retry pattern teaches resilience (GPT-4 not 100% reliable)
- Temperature=0.0 maximizes consistency for educational reproducibility
- Schema in prompt helps GPT-4 understand exact output format
- Works on Azure OpenAI today (no dependency on unreleased features)

**When to use Function Calling** (alternative):
- For **risk analysis agent**: Function definition makes multi-factor output clearer
```python
functions = [{
    "name": "analyze_risk",
    "parameters": {
        "type": "object",
        "properties": {
            "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
            "risk_factors": {"type": "array", "items": {"type": "string"}},
            "mitigating_factors": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["risk_level", "risk_factors", "mitigating_factors"]
    }
}]
```
- Benefit: OpenAI validates enum (risk_level must be low/medium/high)
- Use selectively where schema is complex or enums critical

**Alternatives Considered**:
- ❌ **No structured output**: Parse free-form text, brittle, error-prone
- ❌ **Structured Outputs API**: Not available on Azure yet, would be best choice when released
- ❌ **Always function calling**: More verbose API calls, harder for learners to understand
- ❌ **No retry logic**: Fails ~5% of time with GPT-4, poor learner experience

**References**:
- Pydantic v2: https://docs.pydantic.dev/latest/
- OpenAI JSON mode: https://platform.openai.com/docs/guides/structured-outputs
- Azure OpenAI: https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/json-mode

---

## Summary of Key Decisions

| Decision Area | Choice | Primary Rationale |
|---------------|--------|-------------------|
| **Document Extraction** | Azure Document Intelligence (Invoice/Tax/ID models) | Cost-effective ($0.001/page), structured extraction, confidence scoring |
| **Field Normalization** | GPT-4o Text Mode | Cheap ($0.0001/1K tokens), fast, handles field standardization and derived calculations |
| **State Management** | LangGraph with TypedDict ApplicationState | Simple, functional, leverages framework's strengths |
| **Vector Database** | Azure AI Search Free Tier (hybrid search) | Sufficient capacity, no cost, teaches Azure ecosystem |
| **Experiment Tracking** | MLflow (SQLite + local artifacts) | Zero-config, industry standard, rich comparison UI |
| **Structured Output** | JSON Mode + Pydantic + Retry | Works on Azure, learner-friendly, reliable with retry |
| **Chunking Strategy** | 500 tokens with 50 overlap | Semantic coherence + context preservation |
| **Agent Communication** | State-only (no direct calls) | Clean separation, debuggable, follows LangGraph patterns |

All decisions prioritize **learning value**, **cost-effectiveness**, and **simplicity** for educational research use.

---

## Open Questions / Future Research

1. **Custom Document Intelligence models**: If extraction quality issues arise, analyze confidence patterns - worth training custom models for specific document types?
2. **Prompt versioning**: Should prompts be in separate config files (YAML) or inline in notebooks for transparency?
3. **Multi-document applications**: Current design assumes 1-2 docs per app - how to scale to 10+ documents per applicant?
4. **GPT-4o vs GPT-4o-mini**: Cost/quality tradeoff for normalization and validation - worth testing cheaper model?

These can be revisited during implementation based on learner needs and observed patterns.
