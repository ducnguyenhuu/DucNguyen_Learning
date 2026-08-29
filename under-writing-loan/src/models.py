"""
Pydantic v2 data models for Multi-Agent AI Loan Underwriting System.

This module defines all core data structures used throughout the underwriting
workflow. Models enforce validation, type safety, and provide clear contracts
between agents and external systems.

Design Principles:
- Immutability where possible (frozen models for outputs)
- Clear validation rules with business logic constraints
- Optional vs Required fields for fail-fast validation
- Decimal for monetary values (avoid float precision issues)
- ISO 8601 datetime strings for serialization

Models:
1. LoanApplication - Input entity from applicant
2. ExtractedDocument - Output from Document Agent
3. CreditReport - Data from MCP credit bureau
4. RiskAssessment - Output from Risk Agent
5. ComplianceReport - Output from Compliance Agent
6. LendingDecision - Final output from Decision Agent
7. ApplicationState - LangGraph orchestration state (TypedDict)
8. PolicyDocument - RAG system policy entity

Task: T009 - Create src/models.py with all 8 Pydantic schemas
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Dict, Any, TypedDict
from datetime import datetime
from decimal import Decimal
from enum import Enum


# ============================================================================
# Document Type Enum
# ============================================================================

class DocumentType(str, Enum):
    """
    Supported document types for loan underwriting.
    
    Each type maps to specific Azure Document Intelligence prebuilt models
    and validation rules. Used throughout the document processing pipeline.
    
    Inherits from str to maintain JSON serialization compatibility while
    providing type safety and IDE autocomplete.
    """
    PAY_STUB = "pay_stub"
    BANK_STATEMENT = "bank_statement"
    TAX_RETURN = "tax_return"
    DRIVERS_LICENSE = "drivers_license"
    EMPLOYMENT_LETTER = "employment_letter"


# ============================================================================
# 1. LoanApplication - Input Entity
# ============================================================================

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
        return (self.requested_amount / self.property_value * 100).quantize(Decimal('0.01'))
    
    model_config = ConfigDict(
        json_schema_extra={
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
                    "data/applications/app-001/paystub.pdf",
                    "data/applications/app-001/bank_statement.pdf",
                    "data/applications/app-001/w2.pdf"
                ],
                "submitted_at": "2025-11-19T10:30:00Z",
                "status": "pending"
            }
        }
    )


# ============================================================================
# 2. ExtractedDocument - Document Agent Output
# ============================================================================

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
        description="document_intelligence, gpt4o, or hybrid"
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
    validation_errors: List[str] = Field(
        default_factory=list,
        description="Any issues found during extraction"
    )
    is_valid: bool = Field(
        default=True,
        description="False if critical fields missing or confidence too low"
    )
    
    model_config = ConfigDict(
        frozen=True,  # Immutable after extraction
        json_schema_extra={
            "example": {
                "document_id": "DOC-001-1",
                "application_id": "APP-2025-001",
                "document_type": "pay_stub",
                "file_path": "data/applications/app-001/paystub.pdf",
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
    )


# ============================================================================
# 3. CreditReport - MCP Server Data
# ============================================================================

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
    
    model_config = ConfigDict(
        frozen=True,  # Immutable after retrieval
        json_schema_extra={
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
    )


# ============================================================================
# 4. RiskAssessment - Risk Agent Output
# ============================================================================

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
    
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
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
    )


# ============================================================================
# 5. ComplianceReport - Compliance Agent Output
# ============================================================================

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
    
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
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
    )


# ============================================================================
# 6. LendingDecision - Decision Agent Output
# ============================================================================

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
    
    model_config = ConfigDict(
        frozen=True,
        json_schema_extra={
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
    )


# ============================================================================
# 7. ApplicationState - LangGraph Orchestration State
# ============================================================================

class ApplicationState(TypedDict):
    """
    LangGraph state for multi-agent loan underwriting workflow.
    
    Accumulates data as workflow progresses through agents.
    This is NOT a Pydantic model - LangGraph uses TypedDict for state.
    
    State progression:
    1. Initial: loan_application loaded, all outputs None
    2. After Document Agent: extracted_documents populated
    3. After Risk Agent: credit_report + risk_assessment populated
    4. After Compliance Agent: compliance_report populated
    5. After Decision Agent: lending_decision populated, current_agent="complete"
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


# ============================================================================
# 8. PolicyDocument - RAG System Entity
# ============================================================================

class PolicyDocument(BaseModel):
    """
    Lending policy document stored in Azure AI Search.
    
    Represents a chunked section of policy for RAG retrieval.
    Each chunk is ~500 tokens with 50-token overlap.
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
    
    # Searchability
    keywords: List[str] = Field(
        default_factory=list,
        description="Important terms for keyword search (DTI, LTV, PMI, etc.)"
    )
    
    # Versioning
    effective_date: str = Field(..., description="ISO date when policy became effective")
    supersedes: Optional[str] = Field(None, description="Previous version ID if applicable")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chunk_id": "POL-UW-001-chunk-3",
                "document_title": "Underwriting Standards Policy",
                "document_version": "v2.1",
                "content": "Section 3.2: Debt-to-Income Ratio Guidelines\n\nMaximum DTI for conventional loans is 36% for front-end ratio and 43% for back-end ratio. Exceptions may be granted for DTI up to 45% with strong compensating factors including:\n- Credit score above 740\n- Cash reserves exceeding 6 months PITI\n- Down payment > 20%\n- Stable employment history > 2 years with same employer",
                "category": "credit_requirements",
                "chunk_index": 2,
                "total_chunks": 12,
                "keywords": ["DTI", "debt-to-income", "36%", "43%", "compensating factors", "credit score"],
                "effective_date": "2025-01-01",
                "supersedes": "POL-UW-001-v2.0-chunk-3"
            }
        }
    )


# ============================================================================
# Utility Functions
# ============================================================================

def validate_application_data(data: dict) -> LoanApplication:
    """
    Validate and parse loan application data.
    
    Args:
        data: Raw dictionary from user input or API
        
    Returns:
        Validated LoanApplication instance
        
    Raises:
        ValidationError: If data doesn't match schema
    """
    return LoanApplication.model_validate(data)


def serialize_for_mlflow(model: BaseModel) -> dict:
    """
    Convert Pydantic model to dict for MLflow artifact logging.
    
    Args:
        model: Any Pydantic model instance
        
    Returns:
        JSON-serializable dictionary
    """
    return model.model_dump(mode='json')


# ============================================================================
# Module Exports
# ============================================================================

__all__ = [
    # Core models
    'LoanApplication',
    'ExtractedDocument',
    'CreditReport',
    'RiskAssessment',
    'ComplianceReport',
    'LendingDecision',
    'ApplicationState',
    'PolicyDocument',
    # Sub-models
    'PolicyViolation',
    # Utilities
    'validate_application_data',
    'serialize_for_mlflow',
]
