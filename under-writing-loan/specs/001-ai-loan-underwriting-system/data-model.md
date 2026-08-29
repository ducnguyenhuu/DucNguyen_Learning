# Data Model Specification

**Feature**: Multi-Agent AI Loan Underwriting System  
**Date**: November 19, 2025  
**Status**: Complete

## Overview

This document defines Pydantic v2 data models for all entities in the loan underwriting system. Models enforce validation, type safety, and provide clear contracts between agents and external systems.

**Design Principles**:
- **Immutability where possible**: Use frozen models for outputs to prevent accidental modification
- **Clear validation rules**: Business logic constraints documented and enforced
- **Optional vs Required**: Required fields fail fast, optional fields enable partial processing
- **Datetime handling**: ISO 8601 strings for serialization, datetime objects internally
- **Decimal for money**: Avoid floating-point precision issues in financial calculations

---

## 1. LoanApplication

**Purpose**: Input entity representing applicant-submitted loan application data

```python
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

class LoanApplication(BaseModel):
    """
    Loan application submitted by applicant.
    
    This is the initial input to the underwriting workflow.
    Contains applicant metadata and references to uploaded documents.
    """
    
    # Identity
    application_id: str = Field(
        ..., 
        description="Unique identifier (e.g., 'APP-2025-001')",
        pattern=r'^APP-\d{4}-\d{3}$'
    )
    
    # Applicant Information
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    ssn: str = Field(
        ..., 
        description="Social Security Number (XXX-XX-XXXX format)",
        pattern=r'^\d{3}-\d{2}-\d{4}$'
    )
    date_of_birth: str = Field(
        ..., 
        description="ISO date (YYYY-MM-DD)",
        pattern=r'^\d{4}-\d{2}-\d{2}$'
    )
    email: str = Field(..., pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    phone: str = Field(..., pattern=r'^\+?1?\d{10,15}$')
    
    # Loan Details
    requested_amount: Decimal = Field(
        ..., 
        gt=0,
        le=Decimal("5000000.00"),  # Max $5M
        description="Requested loan amount in USD"
    )
    loan_purpose: str = Field(
        ..., 
        description="Purchase, Refinance, Cash-out Refinance, etc."
    )
    property_type: str = Field(
        ...,
        description="Single Family, Condo, Multi-family, etc."
    )
    property_value: Decimal = Field(
        ...,
        gt=0,
        description="Estimated property value in USD"
    )
    down_payment: Decimal = Field(
        ...,
        ge=0,
        description="Down payment amount in USD"
    )
    
    # Documents
    document_paths: List[str] = Field(
        ..., 
        min_length=1,
        description="Paths to uploaded documents (pay stubs, bank statements, tax returns, ID)"
    )
    
    # Metadata
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="pending", pattern=r'^(pending|processing|completed|rejected)$')
    
    @field_validator('property_value', 'down_payment')
    @classmethod
    def round_currency(cls, v: Decimal) -> Decimal:
        """Round currency to 2 decimal places."""
        return v.quantize(Decimal('0.01'))
    
    @field_validator('requested_amount')
    @classmethod
    def validate_loan_amount(cls, v: Decimal) -> Decimal:
        """Ensure loan amount is reasonable."""
        if v < Decimal("10000.00"):
            raise ValueError("Loan amount must be at least $10,000")
        return v.quantize(Decimal('0.01'))
    
    def calculate_ltv(self) -> Decimal:
        """Calculate Loan-to-Value ratio."""
        loan_amount = self.requested_amount + (self.property_value - self.down_payment) - self.requested_amount
        return (self.requested_amount / self.property_value * 100).quantize(Decimal('0.01'))
    
    class Config:
        json_schema_extra = {
            "example": {
                "application_id": "APP-2025-001",
                "first_name": "Jane",
                "last_name": "Doe",
                "ssn": "123-45-6789",
                "date_of_birth": "1985-06-15",
                "email": "jane.doe@example.com",
                "phone": "+15551234567",
                "requested_amount": "350000.00",
                "loan_purpose": "Purchase",
                "property_type": "Single Family",
                "property_value": "425000.00",
                "down_payment": "75000.00",
                "document_paths": [
                    "data/uploaded/app-001/paystub.pdf",
                    "data/uploaded/app-001/bank_statement.pdf",
                    "data/uploaded/app-001/w2.pdf"
                ],
                "submitted_at": "2025-11-19T10:30:00Z",
                "status": "pending"
            }
        }
```

**Relationships**:
- **One-to-many**: `LoanApplication` → `ExtractedDocument` (multiple documents per application)
- **One-to-one**: `LoanApplication` → `CreditReport` (retrieved via SSN)
- **One-to-one**: `LoanApplication` → `LendingDecision` (final output)

---

## 2. ExtractedDocument

**Purpose**: Output from Document Agent after OCR and structured extraction

```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

class ExtractedDocument(BaseModel):
    """
    Document processed by Document Agent (OCR + GPT-4 extraction).
    
    Contains structured data extracted from uploaded files.
    Multiple documents may exist per application.
    """
    
    # Identity
    document_id: str = Field(..., description="Unique ID (e.g., 'DOC-001-1')")
    application_id: str = Field(..., description="Parent application ID")
    document_type: str = Field(
        ..., 
        description="pay_stub, bank_statement, tax_return, drivers_license, employment_letter"
    )
    file_path: str = Field(..., description="Original file location")
    
    # Extraction Metadata
    extraction_method: str = Field(
        ..., 
        description="document_intelligence, gpt4_vision, or hybrid"
    )
    confidence_score: Optional[float] = Field(
        None, 
        ge=0.0, 
        le=1.0,
        description="Document Intelligence confidence (if applicable)"
    )
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Structured Data (varies by document_type)
    structured_data: Dict[str, Any] = Field(
        ..., 
        description="Extracted fields (schema depends on document_type)"
    )
    
    # Raw OCR Text (for debugging)
    raw_text: Optional[str] = Field(None, description="Full OCR text output")
    
    # Validation
    validation_errors: list[str] = Field(
        default_factory=list,
        description="Any issues found during extraction"
    )
    is_valid: bool = Field(
        default=True,
        description="False if critical fields missing or confidence too low"
    )
    
    class Config:
        frozen = True  # Immutable after extraction
        json_schema_extra = {
            "example": {
                "document_id": "DOC-001-1",
                "application_id": "APP-2025-001",
                "document_type": "pay_stub",
                "file_path": "data/uploaded/app-001/paystub.pdf",
                "extraction_method": "document_intelligence",
                "confidence_score": 0.92,
                "extracted_at": "2025-11-19T10:35:00Z",
                "structured_data": {
                    "employer_name": "Acme Corp",
                    "employer_address": "123 Main St, City, ST 12345",
                    "employee_name": "Jane Doe",
                    "gross_income": 8500.00,
                    "net_income": 6200.00,
                    "pay_period_start": "2025-10-01",
                    "pay_period_end": "2025-10-31",
                    "ytd_gross": 102000.00,
                    "ytd_taxes": 22000.00,
                    "ytd_deductions": 3500.00
                },
                "raw_text": "Acme Corp\\nPay Stub\\n...",
                "validation_errors": [],
                "is_valid": True
            }
        }
```

**Structured Data Schemas by Document Type**:

### Pay Stub
```python
{
    "employer_name": str,
    "employee_name": str,
    "gross_income": float,        # Monthly gross
    "net_income": float,          # Monthly net
    "pay_period_start": str,      # ISO date
    "pay_period_end": str,        # ISO date
    "ytd_gross": float,           # Year-to-date totals
    "ytd_taxes": float,
    "ytd_deductions": float
}
```

### Bank Statement
```python
{
    "account_holder": str,
    "account_number": str,        # Masked (last 4 digits)
    "statement_period_start": str,
    "statement_period_end": str,
    "beginning_balance": float,
    "ending_balance": float,
    "total_deposits": float,
    "total_withdrawals": float,
    "average_balance": float      # Calculated if not provided
}
```

### Tax Return (W-2)
```python
{
    "employee_name": str,
    "employer_name": str,
    "employer_ein": str,
    "tax_year": int,
    "wages": float,               # Box 1
    "federal_withholding": float, # Box 2
    "social_security_wages": float, # Box 3
    "medicare_wages": float       # Box 5
}
```

### Driver's License
```python
{
    "full_name": str,
    "date_of_birth": str,
    "license_number": str,
    "issue_date": str,
    "expiration_date": str,
    "address": str,
    "state": str
}
```

---

## 3. CreditReport

**Purpose**: Credit bureau data retrieved via MCP server

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CreditReport(BaseModel):
    """
    Credit report from mock credit bureau (MCP server).
    
    Represents applicant's credit history for risk assessment.
    """
    
    # Identity
    ssn: str = Field(..., description="Social Security Number (matches LoanApplication)")
    report_date: datetime = Field(default_factory=datetime.utcnow)
    
    # Credit Metrics
    credit_score: int = Field(..., ge=300, le=850, description="FICO score")
    credit_utilization: float = Field(
        ..., 
        ge=0.0, 
        le=100.0,
        description="Percentage of available credit used"
    )
    accounts_open: int = Field(..., ge=0, description="Number of active credit accounts")
    derogatory_marks: int = Field(..., ge=0, description="Collections, bankruptcies, etc.")
    credit_age_months: int = Field(..., ge=0, description="Age of oldest account")
    
    # Payment History
    payment_history: str = Field(
        ..., 
        description="excellent, good, fair, poor based on on-time payments"
    )
    late_payments_12mo: int = Field(default=0, ge=0, description="Late payments in last 12 months")
    
    # Inquiries
    hard_inquiries_12mo: int = Field(default=0, ge=0, description="Hard credit pulls in last year")
    
    # Source
    bureau_source: str = Field(default="mock_credit_bureau", description="Data source identifier")
    
    class Config:
        frozen = True  # Immutable after retrieval
        json_schema_extra = {
            "example": {
                "ssn": "123-45-6789",
                "report_date": "2025-11-19T10:40:00Z",
                "credit_score": 720,
                "credit_utilization": 28.5,
                "accounts_open": 8,
                "derogatory_marks": 0,
                "credit_age_months": 84,
                "payment_history": "good",
                "late_payments_12mo": 1,
                "hard_inquiries_12mo": 2,
                "bureau_source": "mock_credit_bureau"
            }
        }
```

---

## 4. RiskAssessment

**Purpose**: Output from Risk Agent analyzing creditworthiness

```python
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime
from decimal import Decimal

class RiskAssessment(BaseModel):
    """
    Risk analysis output from Risk Agent.
    
    Uses credit report + extracted financial data to assess loan risk.
    """
    
    # Identity
    application_id: str = Field(..., description="Parent application ID")
    assessed_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Risk Level
    risk_level: str = Field(
        ..., 
        pattern=r'^(low|medium|high)$',
        description="Overall risk classification"
    )
    risk_score: float = Field(
        ..., 
        ge=0.0, 
        le=100.0,
        description="Numeric risk score (0=lowest risk, 100=highest risk)"
    )
    
    # Financial Metrics
    debt_to_income_ratio: Decimal = Field(
        ..., 
        ge=0.0,
        description="DTI as percentage (e.g., 38.5 for 38.5%)"
    )
    loan_to_value_ratio: Decimal = Field(
        ..., 
        ge=0.0,
        description="LTV as percentage"
    )
    monthly_debt_payments: Decimal = Field(..., ge=0.0)
    monthly_gross_income: Decimal = Field(..., gt=0.0)
    
    # Analysis
    risk_factors: List[str] = Field(
        ..., 
        description="Factors increasing risk (e.g., 'High DTI: 42%')"
    )
    mitigating_factors: List[str] = Field(
        ...,
        description="Factors reducing risk (e.g., 'Excellent credit score: 780')"
    )
    
    # Reasoning
    reasoning: str = Field(
        ..., 
        min_length=50,
        description="Detailed explanation of risk assessment from GPT-4"
    )
    
    # Recommendation
    recommendation: str = Field(
        ..., 
        pattern=r'^(approve|review|deny)$',
        description="Agent's recommendation for next steps"
    )
    
    class Config:
        frozen = True
        json_schema_extra = {
            "example": {
                "application_id": "APP-2025-001",
                "assessed_at": "2025-11-19T10:45:00Z",
                "risk_level": "medium",
                "risk_score": 42.0,
                "debt_to_income_ratio": "38.50",
                "loan_to_value_ratio": "82.35",
                "monthly_debt_payments": "2800.00",
                "monthly_gross_income": "7250.00",
                "risk_factors": [
                    "DTI above 36% threshold (38.5%)",
                    "LTV above 80% (82.35%)",
                    "One late payment in last 12 months"
                ],
                "mitigating_factors": [
                    "Good credit score: 720",
                    "Low credit utilization: 28.5%",
                    "8 years credit history",
                    "Stable employment with Acme Corp"
                ],
                "reasoning": "Applicant shows stable income and good credit history, but DTI and LTV ratios slightly exceed conservative thresholds. The single late payment is concerning but offset by otherwise clean payment history. Recommend manual review for potential approval with conditions.",
                "recommendation": "review"
            }
        }
```

---

## 5. ComplianceReport

**Purpose**: Output from Compliance Agent checking policy adherence

```python
from pydantic import BaseModel, Field
from typing import List, Dict
from datetime import datetime

class PolicyViolation(BaseModel):
    """Individual policy violation or concern."""
    policy_name: str = Field(..., description="Name of violated policy")
    policy_section: str = Field(..., description="Specific section/rule")
    severity: str = Field(..., pattern=r'^(critical|warning|info)$')
    description: str = Field(..., description="What was violated and why")
    recommendation: str = Field(..., description="How to remediate")

class ComplianceReport(BaseModel):
    """
    Compliance check output from Compliance Agent.
    
    Validates application against lending policies via RAG.
    """
    
    # Identity
    application_id: str = Field(..., description="Parent application ID")
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Compliance Status
    is_compliant: bool = Field(..., description="True if no critical violations")
    compliance_score: float = Field(
        ..., 
        ge=0.0, 
        le=100.0,
        description="0-100 score (100=fully compliant)"
    )
    
    # Violations
    violations: List[PolicyViolation] = Field(
        default_factory=list,
        description="List of policy violations found"
    )
    
    # Policies Checked
    policies_evaluated: List[str] = Field(
        ...,
        description="Policy documents retrieved from RAG system"
    )
    rag_chunks_used: int = Field(..., ge=0, description="Number of policy chunks retrieved")
    
    # Reasoning
    compliance_summary: str = Field(
        ..., 
        min_length=50,
        description="Overall compliance assessment from GPT-4"
    )
    
    # RAG Context
    relevant_policy_excerpts: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Key policy sections used in evaluation"
    )
    
    class Config:
        frozen = True
        json_schema_extra = {
            "example": {
                "application_id": "APP-2025-001",
                "checked_at": "2025-11-19T10:50:00Z",
                "is_compliant": False,
                "compliance_score": 75.0,
                "violations": [
                    {
                        "policy_name": "Underwriting Standards Policy",
                        "policy_section": "Section 3.2: Debt-to-Income Limits",
                        "severity": "warning",
                        "description": "DTI of 38.5% exceeds standard threshold of 36% for conventional loans",
                        "recommendation": "Consider compensating factors or require additional reserves"
                    },
                    {
                        "policy_name": "LTV Guidelines",
                        "policy_section": "Section 2.1: Maximum LTV Ratios",
                        "severity": "warning",
                        "description": "LTV of 82.35% exceeds 80% for non-FHA loans without PMI",
                        "recommendation": "Require private mortgage insurance or larger down payment"
                    }
                ],
                "policies_evaluated": [
                    "Underwriting Standards Policy v2.1",
                    "Credit Score Requirements",
                    "LTV Guidelines"
                ],
                "rag_chunks_used": 5,
                "compliance_summary": "Application has 2 warnings but no critical violations. DTI and LTV both slightly exceed standard thresholds but are within acceptable range with compensating factors (good credit, stable income). PMI would address LTV concern.",
                "relevant_policy_excerpts": [
                    {
                        "policy": "Underwriting Standards Policy",
                        "excerpt": "Maximum DTI for conventional loans is 36%. DTI up to 43% may be considered with compensating factors..."
                    }
                ]
            }
        }
```

---

## 6. LendingDecision

**Purpose**: Final output from Decision Agent

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

class LendingDecision(BaseModel):
    """
    Final underwriting decision from Decision Agent.
    
    Synthesizes risk assessment and compliance report into actionable decision.
    """
    
    # Identity
    application_id: str = Field(..., description="Parent application ID")
    decision_made_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Decision
    decision: str = Field(
        ..., 
        pattern=r'^(approved|conditional_approval|denied|refer_to_manual)$',
        description="Final lending decision"
    )
    decision_confidence: float = Field(
        ..., 
        ge=0.0, 
        le=1.0,
        description="Agent's confidence in decision (0.0-1.0)"
    )
    
    # Loan Terms (if approved/conditional)
    approved_amount: Optional[Decimal] = Field(None, description="May differ from requested")
    interest_rate: Optional[Decimal] = Field(None, ge=0.0, description="APR as percentage")
    loan_term_months: Optional[int] = Field(None, gt=0, description="120, 180, 240, 360")
    monthly_payment: Optional[Decimal] = Field(None, ge=0.0)
    
    # Conditions (if conditional_approval)
    conditions: List[str] = Field(
        default_factory=list,
        description="Requirements for final approval (e.g., 'Provide proof of PMI')"
    )
    
    # Denial Reasons (if denied)
    denial_reasons: List[str] = Field(
        default_factory=list,
        description="Specific reasons for denial per regulations"
    )
    
    # Reasoning
    decision_summary: str = Field(
        ..., 
        min_length=100,
        description="Comprehensive explanation of decision from GPT-4"
    )
    
    # Supporting Data
    risk_level: str = Field(..., description="From RiskAssessment")
    compliance_score: float = Field(..., description="From ComplianceReport")
    key_factors: List[str] = Field(
        ...,
        description="Top factors influencing decision (positive and negative)"
    )
    
    # Metadata
    agent_version: str = Field(default="v1.0", description="Agent version for reproducibility")
    
    class Config:
        frozen = True
        json_schema_extra = {
            "example": {
                "application_id": "APP-2025-001",
                "decision_made_at": "2025-11-19T10:55:00Z",
                "decision": "conditional_approval",
                "decision_confidence": 0.82,
                "approved_amount": "350000.00",
                "interest_rate": "6.75",
                "loan_term_months": 360,
                "monthly_payment": "2270.00",
                "conditions": [
                    "Provide proof of private mortgage insurance (PMI) for LTV > 80%",
                    "Obtain written employment verification dated within 30 days of closing",
                    "Maintain credit score above 680 through closing"
                ],
                "denial_reasons": [],
                "decision_summary": "Applicant demonstrates strong creditworthiness with good credit score (720) and stable employment. DTI (38.5%) and LTV (82.35%) slightly exceed standard thresholds but remain within acceptable range for conditional approval. Key conditions: PMI required for LTV > 80%, employment reverification due to processing timeline. Approved at requested amount with market-rate interest. Low risk of default based on payment history and income stability.",
                "risk_level": "medium",
                "compliance_score": 75.0,
                "key_factors": [
                    "Positive: Good credit score (720)",
                    "Positive: Stable 8-year employment history",
                    "Positive: Low credit utilization (28.5%)",
                    "Concern: DTI at 38.5% (above 36% threshold)",
                    "Concern: LTV at 82.35% (requires PMI)",
                    "Minor: 1 late payment in last 12 months"
                ],
                "agent_version": "v1.0"
            }
        }
```

---

## 7. ApplicationState (LangGraph)

**Purpose**: Orchestration state for LangGraph multi-agent workflow

```python
from typing import TypedDict, Optional, List, Dict
from datetime import datetime

class ApplicationState(TypedDict):
    """
    LangGraph state for multi-agent loan underwriting workflow.
    
    Accumulates data as workflow progresses through agents.
    This is NOT a Pydantic model - LangGraph uses TypedDict for state.
    """
    
    # Identity
    application_id: str
    started_at: datetime
    
    # Input
    loan_application: dict  # Serialized LoanApplication
    
    # Agent Outputs (accumulated)
    extracted_documents: Optional[List[dict]]  # List of ExtractedDocument dicts
    credit_report: Optional[dict]              # CreditReport dict
    risk_assessment: Optional[dict]            # RiskAssessment dict
    compliance_report: Optional[dict]          # ComplianceReport dict
    lending_decision: Optional[dict]           # LendingDecision dict
    
    # Workflow Metadata
    current_agent: str                         # "document", "risk", "compliance", "decision", "complete"
    errors: List[str]                          # Accumulated errors (workflow continues if possible)
    execution_times: Dict[str, float]          # Agent name → execution time in seconds
    
    # MLflow Tracking
    mlflow_run_id: Optional[str]               # Active MLflow run for this application
    
    # Cost Tracking
    total_tokens_used: int
    total_cost_usd: float

# Example state progression:
"""
Initial State:
{
    "application_id": "APP-2025-001",
    "started_at": datetime(2025, 11, 19, 10, 30),
    "loan_application": {...},
    "extracted_documents": None,
    "credit_report": None,
    "risk_assessment": None,
    "compliance_report": None,
    "lending_decision": None,
    "current_agent": "document",
    "errors": [],
    "execution_times": {},
    "mlflow_run_id": None,
    "total_tokens_used": 0,
    "total_cost_usd": 0.0
}

After Document Agent:
{
    ...previous fields...
    "extracted_documents": [{...}, {...}, {...}],
    "current_agent": "risk",
    "execution_times": {"document": 12.5},
    "total_tokens_used": 2500,
    "total_cost_usd": 0.05
}

After Complete Workflow:
{
    ...previous fields...
    "lending_decision": {...},
    "current_agent": "complete",
    "execution_times": {
        "document": 12.5,
        "risk": 8.2,
        "compliance": 15.3,
        "decision": 6.1
    },
    "total_tokens_used": 12500,
    "total_cost_usd": 0.25
}
"""
```

**State Management Notes**:
- **Not a Pydantic model**: LangGraph uses TypedDict for efficiency (no validation overhead during transitions)
- **Validation at boundaries**: Convert to/from Pydantic models when entering/exiting agents
- **Accumulative pattern**: Agents add to state, never remove (preserves audit trail)
- **Error handling**: Errors list allows workflow to continue collecting partial results

---

## 8. PolicyDocument

**Purpose**: RAG system entity for lending policy documents

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class PolicyDocument(BaseModel):
    """
    Lending policy document stored in Azure AI Search.
    
    Represents a chunked section of policy for RAG retrieval.
    """
    
    # Identity
    chunk_id: str = Field(..., description="Unique ID (e.g., 'POL-UW-001-chunk-5')")
    document_title: str = Field(..., description="Policy document name")
    document_version: str = Field(..., description="Version number (e.g., 'v2.1')")
    
    # Content
    content: str = Field(
        ..., 
        min_length=50,
        max_length=2000,
        description="Policy text chunk (500 tokens ≈ 375 words)"
    )
    
    # Metadata
    category: str = Field(
        ..., 
        description="credit_requirements, income_verification, property_guidelines, etc."
    )
    chunk_index: int = Field(..., ge=0, description="Position in original document")
    total_chunks: int = Field(..., gt=0, description="Total chunks in document")
    
    # Vector Embedding (not stored in Pydantic, computed separately)
    # embedding: List[float]  # 1536 dimensions for Ada-002 (stored in Azure AI Search)
    
    # Searchability
    keywords: List[str] = Field(
        default_factory=list,
        description="Important terms for keyword search (DTI, LTV, PMI, etc.)"
    )
    
    # Versioning
    effective_date: str = Field(..., description="ISO date when policy became effective")
    supersedes: Optional[str] = Field(None, description="Previous version ID if applicable")
    
    class Config:
        json_schema_extra = {
            "example": {
                "chunk_id": "POL-UW-001-chunk-3",
                "document_title": "Underwriting Standards Policy",
                "document_version": "v2.1",
                "content": "Section 3.2: Debt-to-Income Ratio Guidelines\n\nMaximum DTI for conventional loans is 36% for front-end ratio and 43% for back-end ratio. Exceptions may be granted for DTI up to 45% with strong compensating factors including:\n- Credit score above 740\n- Cash reserves exceeding 6 months PITI\n- Down payment > 20%\n- Stable employment history > 2 years with same employer\n\nAll DTI calculations must use gross monthly income and include all monthly debt obligations as reported on credit report.",
                "category": "credit_requirements",
                "chunk_index": 2,
                "total_chunks": 12,
                "keywords": ["DTI", "debt-to-income", "36%", "43%", "compensating factors", "credit score"],
                "effective_date": "2025-01-01",
                "supersedes": "POL-UW-001-v2.0-chunk-3"
            }
        }
```

**Azure AI Search Index Mapping**:
```json
{
  "name": "lending-policies-index",
  "fields": [
    {"name": "chunk_id", "type": "Edm.String", "key": true},
    {"name": "content", "type": "Edm.String", "searchable": true},
    {"name": "embedding", "type": "Collection(Edm.Single)", "dimensions": 1536, "vectorSearchProfile": "vector-profile"},
    {"name": "document_title", "type": "Edm.String", "filterable": true, "facetable": true},
    {"name": "category", "type": "Edm.String", "filterable": true, "facetable": true},
    {"name": "keywords", "type": "Collection(Edm.String)", "searchable": true},
    {"name": "chunk_index", "type": "Edm.Int32", "sortable": true},
    {"name": "effective_date", "type": "Edm.String", "filterable": true}
  ]
}
```

---

## Validation Examples

### Test Case 1: Valid Application
```python
app = LoanApplication(
    application_id="APP-2025-001",
    first_name="Jane",
    last_name="Doe",
    ssn="123-45-6789",
    date_of_birth="1985-06-15",
    email="jane@example.com",
    phone="+15551234567",
    requested_amount=Decimal("350000.00"),
    loan_purpose="Purchase",
    property_type="Single Family",
    property_value=Decimal("425000.00"),
    down_payment=Decimal("75000.00"),
    document_paths=["data/uploaded/app-001/paystub.pdf"]
)
# ✅ Valid - all required fields present, passes validation
```

### Test Case 2: Invalid SSN Format
```python
app = LoanApplication(
    ssn="12345678",  # Missing dashes
    # ... other fields
)
# ❌ Raises ValidationError: "String should match pattern '^\\d{3}-\\d{2}-\\d{4}$'"
```

### Test Case 3: Invalid Loan Amount
```python
app = LoanApplication(
    requested_amount=Decimal("5000.00"),  # Too small
    # ... other fields
)
# ❌ Raises ValidationError: "Loan amount must be at least $10,000"
```

### Test Case 4: Risk Assessment with Function Calling
```python
# GPT-4 function definition
risk_function = {
    "name": "create_risk_assessment",
    "parameters": RiskAssessment.model_json_schema()
}

# GPT-4 returns validated JSON matching schema
risk = RiskAssessment.model_validate_json(gpt4_response)
# ✅ Type-safe, validated risk assessment
```

---

## Entity Relationship Diagram

```
LoanApplication (1)
    ├─── ExtractedDocument (1..N)
    ├─── CreditReport (1)
    ├─── RiskAssessment (1)
    ├─── ComplianceReport (1)
    └─── LendingDecision (1)

PolicyDocument (N) ──── (RAG retrieval) ───> ComplianceReport (1)

ApplicationState (LangGraph)
    ├─── Contains: LoanApplication, ExtractedDocument[], CreditReport, 
    │              RiskAssessment, ComplianceReport, LendingDecision
    └─── Orchestrates: document_agent → risk_agent → compliance_agent → decision_agent
```

---

## Usage in Workflow

### Document Agent
**Input**: `LoanApplication.document_paths`  
**Output**: `List[ExtractedDocument]`

### Risk Agent
**Input**: `ExtractedDocument[]`, `CreditReport`  
**Output**: `RiskAssessment`

### Compliance Agent
**Input**: `RiskAssessment`, `PolicyDocument[]` (via RAG)  
**Output**: `ComplianceReport`

### Decision Agent
**Input**: `RiskAssessment`, `ComplianceReport`  
**Output**: `LendingDecision`

### LangGraph Orchestrator
**State**: `ApplicationState` (accumulates all entities)  
**Final Output**: `ApplicationState` with complete workflow results

---

## Implementation Notes

1. **Decimal for Currency**: Always use `Decimal` for monetary amounts to avoid float precision errors
2. **Frozen Models**: Outputs (ExtractedDocument, CreditReport, etc.) are immutable to prevent accidental modification
3. **Validation at Boundaries**: Validate Pydantic models when entering/exiting agents, use TypedDict for LangGraph state
4. **JSON Serialization**: Use `.model_dump_json()` for serialization, `.model_validate_json()` for deserialization
5. **MLflow Logging**: Convert models to dicts with `.model_dump()` before logging as artifacts
6. **Error Handling**: Use `model_validate()` with try/except for graceful degradation if GPT-4 output is malformed

---

**Next Steps**: Define MCP server API contracts in `contracts/mcp-server.yaml` using these schemas as response types.
