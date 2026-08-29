"""
Pytest configuration and fixtures for loan underwriting test suite.

This module provides reusable fixtures for testing all agents in the
multi-agent loan underwriting system. Fixtures cover:

1. Sample Pydantic models (LoanApplication, CreditReport, etc.)
2. Mock Azure clients (OpenAI, Document Intelligence, AI Search)
3. Temporary file system utilities
4. Database connection mocks
5. Configuration and environment variables

Task: T014 - Create comprehensive pytest fixtures in tests/conftest.py

Usage:
    Any test file can import these fixtures automatically:
    
    def test_something(sample_loan_application, mock_azure_openai_client):
        # Fixtures injected automatically
        assert sample_loan_application.credit_score >= 300
"""

import pytest
import sys
from pathlib import Path
from typing import Dict, Any, List, Generator
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock
import tempfile
import shutil

# Add src/ to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from models import (
    LoanApplication,
    ExtractedDocument,
    CreditReport,
    RiskAssessment,
    ComplianceReport,
    PolicyViolation,
    LendingDecision,
    PolicyDocument,
)


# ============================================================================
# Sample Pydantic Model Fixtures
# ============================================================================

@pytest.fixture
def sample_loan_application() -> LoanApplication:
    """
    Sample loan application with good credit profile.
    
    Represents a strong applicant (780 credit score, reasonable DTI).
    Use as default test input for agent workflows.
    """
    return LoanApplication(
        application_id="APP-2025-001",
        first_name="Jane",
        last_name="Doe",
        ssn="111-11-1111",
        date_of_birth="1985-06-15",
        email="jane.doe@example.com",
        phone="+15551234567",
        requested_amount=Decimal("350000.00"),
        loan_purpose="Purchase",
        property_type="Single Family",
        property_value=Decimal("425000.00"),
        down_payment=Decimal("75000.00"),
        document_paths=[
            "tests/sample_applications/paystub.pdf",
            "tests/sample_applications/bank_statement.pdf"
        ],
        submitted_at=datetime(2025, 11, 19, 10, 30),
        status="pending"
    )


@pytest.fixture
def sample_loan_application_poor_credit() -> LoanApplication:
    """
    Sample loan application with poor credit profile (590 score).
    
    Use for testing rejection/denial workflows.
    """
    return LoanApplication(
        application_id="APP-2025-002",
        first_name="John",
        last_name="Smith",
        ssn="444-44-4444",
        date_of_birth="1990-03-20",
        email="john.smith@example.com",
        phone="+15559876543",
        requested_amount=Decimal("200000.00"),
        loan_purpose="Purchase",
        property_type="Condo",
        property_value=Decimal("250000.00"),
        down_payment=Decimal("50000.00"),
        document_paths=[
            "tests/sample_applications/paystub_poor.pdf"
        ],
        submitted_at=datetime(2025, 11, 19, 11, 0),
        status="pending"
    )


@pytest.fixture
def sample_extracted_document() -> ExtractedDocument:
    """
    Sample document extraction from Document Agent (pay stub).
    
    Represents high-confidence OCR extraction via Azure Document Intelligence.
    """
    return ExtractedDocument(
        document_id="DOC-2025-001-1",
        application_id="APP-2025-001",
        document_type="pay_stub",
        file_path="tests/sample_applications/paystub.pdf",
        extraction_method="document_intelligence",
        confidence_score=0.92,
        extracted_at=datetime(2025, 11, 19, 10, 35),
        structured_data={
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
        raw_text="Acme Corp\nPay Stub\nEmployee: Jane Doe\nGross: $8,500.00...",
        validation_errors=[],
        is_valid=True
    )


@pytest.fixture
def sample_credit_report() -> CreditReport:
    """
    Sample credit report with excellent profile (780 score).
    
    Matches "Test Excellent" profile from seed_data.py.
    """
    return CreditReport(
        ssn="111-11-1111",
        report_date=datetime(2025, 11, 19, 10, 40),
        credit_score=780,
        credit_utilization=15.0,
        accounts_open=12,
        derogatory_marks=0,
        credit_age_months=120,
        payment_history="excellent",
        late_payments_12mo=0,
        hard_inquiries_12mo=1,
        bureau_source="mock_credit_bureau"
    )


@pytest.fixture
def sample_credit_report_poor() -> CreditReport:
    """
    Sample credit report with poor profile (590 score).
    
    Use for testing denial workflows.
    """
    return CreditReport(
        ssn="444-44-4444",
        report_date=datetime(2025, 11, 19, 11, 5),
        credit_score=590,
        credit_utilization=85.0,
        accounts_open=4,
        derogatory_marks=3,
        credit_age_months=36,
        payment_history="poor",
        late_payments_12mo=5,
        hard_inquiries_12mo=8,
        bureau_source="mock_credit_bureau"
    )


@pytest.fixture
def sample_risk_assessment() -> RiskAssessment:
    """
    Sample risk assessment with medium risk (borderline case).
    
    DTI slightly high but good credit - typical review case.
    """
    return RiskAssessment(
        application_id="APP-2025-001",
        assessed_at=datetime(2025, 11, 19, 10, 45),
        risk_level="medium",
        risk_score=42.0,
        debt_to_income_ratio=Decimal("38.50"),
        loan_to_value_ratio=Decimal("82.35"),
        monthly_debt_payments=Decimal("2800.00"),
        monthly_gross_income=Decimal("7250.00"),
        risk_factors=[
            "DTI above 36% threshold (38.5%)",
            "LTV above 80% (82.35%)",
            "One late payment in last 12 months"
        ],
        mitigating_factors=[
            "Good credit score: 720",
            "Low credit utilization: 28.5%",
            "8 years credit history",
            "Stable employment with Acme Corp"
        ],
        reasoning="Applicant shows stable income and good credit history, but DTI and LTV ratios slightly exceed conservative thresholds. The single late payment is concerning but offset by otherwise clean payment history. Recommend manual review for potential approval with conditions.",
        recommendation="review"
    )


@pytest.fixture
def sample_compliance_report() -> ComplianceReport:
    """
    Sample compliance report with warnings (not critical violations).
    
    Represents borderline compliance - typical for review cases.
    """
    return ComplianceReport(
        application_id="APP-2025-001",
        checked_at=datetime(2025, 11, 19, 10, 50),
        is_compliant=False,
        compliance_score=75.0,
        violations=[
            PolicyViolation(
                policy_name="Underwriting Standards Policy",
                policy_section="Section 3.2: Debt-to-Income Limits",
                severity="warning",
                description="DTI of 38.5% exceeds standard threshold of 36% for conventional loans",
                recommendation="Consider compensating factors or require additional reserves"
            )
        ],
        policies_evaluated=[
            "Underwriting Standards Policy v2.1",
            "Credit Score Requirements",
            "LTV Guidelines"
        ],
        rag_chunks_used=5,
        compliance_summary="Application has 2 warnings but no critical violations. DTI and LTV both slightly exceed standard thresholds but are within acceptable range with compensating factors (good credit, stable income). PMI would address LTV concern.",
        relevant_policy_excerpts=[
            {
                "policy": "Underwriting Standards Policy",
                "excerpt": "Maximum DTI for conventional loans is 36%. DTI up to 43% may be considered with compensating factors..."
            }
        ]
    )


@pytest.fixture
def sample_lending_decision_approved() -> LendingDecision:
    """
    Sample lending decision: Conditional Approval.
    
    Represents typical borderline approval with conditions.
    """
    return LendingDecision(
        application_id="APP-2025-001",
        decision_made_at=datetime(2025, 11, 19, 10, 55),
        decision="conditional_approval",
        decision_confidence=0.82,
        approved_amount=Decimal("350000.00"),
        interest_rate=Decimal("6.75"),
        loan_term_months=360,
        monthly_payment=Decimal("2270.00"),
        conditions=[
            "Provide proof of private mortgage insurance (PMI) for LTV > 80%",
            "Obtain written employment verification dated within 30 days of closing",
            "Maintain credit score above 680 through closing"
        ],
        denial_reasons=[],
        decision_summary="Applicant demonstrates strong creditworthiness with good credit score (720) and stable employment. DTI (38.5%) and LTV (82.35%) slightly exceed standard thresholds but remain within acceptable range for conditional approval. Key conditions: PMI required for LTV > 80%, employment reverification due to processing timeline. Approved at requested amount with market-rate interest. Low risk of default based on payment history and income stability.",
        risk_level="medium",
        compliance_score=75.0,
        key_factors=[
            "Positive: Good credit score (720)",
            "Positive: Stable 8-year employment history",
            "Positive: Low credit utilization (28.5%)",
            "Concern: DTI at 38.5% (above 36% threshold)",
            "Concern: LTV at 82.35% (requires PMI)",
            "Minor: 1 late payment in last 12 months"
        ],
        agent_version="v1.0"
    )


@pytest.fixture
def sample_lending_decision_rejected() -> LendingDecision:
    """
    Sample lending decision: Denied.
    
    Represents clear rejection case with multiple critical issues.
    """
    return LendingDecision(
        application_id="APP-2025-002",
        decision_made_at=datetime(2025, 11, 19, 11, 10),
        decision="denied",
        decision_confidence=0.95,
        approved_amount=None,
        interest_rate=None,
        loan_term_months=None,
        monthly_payment=None,
        conditions=[],
        denial_reasons=[
            "Credit score below minimum threshold (590 < 620)",
            "DTI ratio exceeds maximum allowable (48% > 43%)",
            "Multiple derogatory marks on credit report"
        ],
        decision_summary="Application does not meet minimum underwriting standards. Credit score of 590 falls below the 620 threshold for conventional loans. DTI of 48% significantly exceeds the maximum allowable 43% even with compensating factors. Credit report shows 3 derogatory marks including recent collection accounts. Insufficient compensating factors to offset these deficiencies. Applicant should work on credit repair and debt reduction before reapplying.",
        risk_level="high",
        compliance_score=45.0,
        key_factors=[
            "Critical: Credit score too low (590 < 620)",
            "Critical: DTI too high (48% > 43%)",
            "Critical: 3 derogatory marks on credit",
            "Negative: Recent collection accounts",
            "Negative: High credit utilization (85%)"
        ],
        agent_version="v1.0"
    )


@pytest.fixture
def sample_policy_document() -> PolicyDocument:
    """
    Sample policy document chunk from RAG system.
    
    Represents a policy chunk stored in Azure AI Search vector store.
    """
    return PolicyDocument(
        chunk_id="POL-UW-001-chunk-3",
        document_title="Underwriting Standards Policy",
        document_version="v2.1",
        content="Section 3.2: Debt-to-Income Ratio Guidelines\n\nMaximum DTI for conventional loans is 36% for front-end ratio and 43% for back-end ratio. Exceptions may be granted for DTI up to 45% with strong compensating factors including:\n- Credit score above 740\n- Cash reserves exceeding 6 months PITI\n- Down payment > 20%\n- Stable employment history > 2 years with same employer",
        category="credit_requirements",
        chunk_index=2,
        total_chunks=12,
        keywords=["DTI", "debt-to-income", "36%", "43%", "compensating factors", "credit score"],
        effective_date="2025-01-01",
        supersedes="POL-UW-001-v2.0-chunk-3"
    )


# ============================================================================
# Mock Azure Client Fixtures
# ============================================================================

@pytest.fixture
def mock_azure_openai_client() -> Mock:
    """
    Mock Azure OpenAI client for GPT-4 completions.
    
    Returns mock responses without actual API calls.
    """
    mock_client = Mock()
    
    # Mock chat completions response
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "This is a mock GPT-4 response for testing purposes."
    mock_response.usage.prompt_tokens = 150
    mock_response.usage.completion_tokens = 50
    mock_response.usage.total_tokens = 200
    
    mock_client.chat.completions.create.return_value = mock_response
    
    return mock_client


@pytest.fixture
def mock_document_intelligence_client() -> Mock:
    """
    Mock Azure Document Intelligence client for OCR.
    
    Simulates document analysis without actual service calls.
    """
    mock_client = Mock()
    
    # Mock analyze_document response
    mock_result = Mock()
    mock_result.content = "Mock OCR text from document..."
    mock_result.key_value_pairs = [
        Mock(key="employer_name", value="Acme Corp"),
        Mock(key="gross_income", value="8500.00")
    ]
    mock_result.confidence = 0.92
    
    mock_client.begin_analyze_document.return_value.result.return_value = mock_result
    
    return mock_client


@pytest.fixture
def mock_search_client() -> Mock:
    """
    Mock Azure AI Search client for RAG policy retrieval.
    
    Returns mock policy chunks without actual search service.
    """
    mock_client = Mock()
    
    # Mock search response with policy chunks
    mock_results = [
        {
            "chunk_id": "POL-UW-001-chunk-3",
            "content": "Maximum DTI is 36%...",
            "score": 0.89
        },
        {
            "chunk_id": "POL-UW-002-chunk-7",
            "content": "Credit score minimum 620...",
            "score": 0.82
        }
    ]
    
    mock_client.search.return_value = mock_results
    
    return mock_client


# ============================================================================
# File System Fixtures
# ============================================================================

@pytest.fixture
def temp_data_dir() -> Generator[Path, None, None]:
    """
    Create temporary data directory for test files.
    
    Automatically cleaned up after test completion.
    
    Yields:
        Path: Temporary directory path
    """
    temp_dir = Path(tempfile.mkdtemp(prefix="loan_test_"))
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_pdf_path(temp_data_dir: Path) -> Path:
    """
    Create a dummy PDF file for testing document processing.
    
    Args:
        temp_data_dir: Temporary directory fixture
        
    Returns:
        Path: Path to dummy PDF file
    """
    pdf_path = temp_data_dir / "test_document.pdf"
    # Create minimal PDF (just for file existence, not valid PDF content)
    pdf_path.write_text("%PDF-1.4\nMock PDF content for testing\n%%EOF")
    return pdf_path


@pytest.fixture
def mock_uploaded_documents(temp_data_dir: Path) -> List[Path]:
    """
    Create multiple mock uploaded documents (various types).
    
    Returns:
        List[Path]: List of document paths
    """
    documents = []
    doc_types = ["paystub.pdf", "bank_statement.pdf", "drivers_license.pdf", "tax_return.pdf"]
    
    for doc_type in doc_types:
        doc_path = temp_data_dir / doc_type
        doc_path.write_text(f"%PDF-1.4\nMock {doc_type}\n%%EOF")
        documents.append(doc_path)
    
    return documents


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def mock_credit_db_connection() -> Mock:
    """
    Mock SQLite connection to credit bureau database.
    
    Returns:
        Mock: Mocked database connection
    """
    mock_conn = Mock()
    mock_cursor = Mock()
    
    # Mock cursor.fetchone() to return credit data
    mock_cursor.fetchone.return_value = (
        "111-11-1111",  # ssn
        780,            # credit_score
        15.0,           # credit_utilization
        12,             # accounts_open
        0,              # derogatory_marks
        120,            # credit_age_months
        "excellent",    # payment_history
        0,              # late_payments_12mo
        1,              # hard_inquiries_12mo
    )
    
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.execute.return_value = mock_cursor
    
    return mock_conn


@pytest.fixture
def mock_application_db_connection() -> Mock:
    """
    Mock SQLite connection to application tracking database.
    
    Returns:
        Mock: Mocked database connection
    """
    mock_conn = Mock()
    mock_cursor = Mock()
    
    # Mock cursor.fetchone() to return application state
    mock_cursor.fetchone.return_value = (
        "APP-2025-001",                    # application_id
        "processing",                      # status
        "2025-11-19T10:30:00Z",           # submitted_at
        True,                              # document_extracted
        True,                              # credit_checked
        False,                             # risk_assessed
        False,                             # compliance_checked
        False,                             # decision_made
        None,                              # final_decision
        None,                              # approved_amount
        15.5,                              # processing_time_seconds
        450,                               # total_tokens_used
        0.025,                             # total_cost_usd
    )
    
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.execute.return_value = mock_cursor
    
    return mock_conn


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def mock_env_vars(monkeypatch) -> Dict[str, str]:
    """
    Mock environment variables for Azure services.
    
    Sets fake credentials to prevent actual API calls.
    
    Args:
        monkeypatch: Pytest's monkeypatch fixture
        
    Returns:
        Dict[str, str]: Dictionary of mocked environment variables
    """
    env_vars = {
        "AZURE_OPENAI_ENDPOINT": "https://mock-openai.openai.azure.com/",
        "AZURE_OPENAI_KEY": "mock-api-key-12345",
        "AZURE_OPENAI_DEPLOYMENT": "gpt-4o",
        "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT": "https://mock-docint.cognitiveservices.azure.com/",
        "AZURE_DOCUMENT_INTELLIGENCE_KEY": "mock-docint-key-67890",
        "AZURE_SEARCH_ENDPOINT": "https://mock-search.search.windows.net/",
        "AZURE_SEARCH_KEY": "mock-search-key-abcde",
        "AZURE_SEARCH_INDEX": "loan-policies",
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars


@pytest.fixture
def sample_application_state() -> Dict[str, Any]:
    """
    Sample LangGraph application state (TypedDict).
    
    Represents workflow state after Risk Agent completion.
    
    Returns:
        Dict[str, Any]: Application state dictionary
    """
    return {
        "application_id": "APP-2025-001",
        "started_at": datetime(2025, 11, 19, 10, 30),
        "loan_application": {
            "application_id": "APP-2025-001",
            "first_name": "Jane",
            "last_name": "Doe",
            "ssn": "111-11-1111",
            "requested_amount": "350000.00",
            "property_value": "425000.00"
        },
        "extracted_documents": [
            {
                "document_id": "DOC-001-1",
                "document_type": "pay_stub",
                "is_valid": True
            }
        ],
        "credit_report": {
            "ssn": "111-11-1111",
            "credit_score": 780,
            "payment_history": "excellent"
        },
        "risk_assessment": {
            "application_id": "APP-2025-001",
            "risk_level": "medium",
            "recommendation": "review"
        },
        "compliance_report": None,
        "lending_decision": None,
        "current_agent": "compliance",
        "errors": [],
        "execution_times": {
            "document_agent": 2.5,
            "risk_agent": 1.8
        },
        "mlflow_run_id": "mock-run-id-12345",
        "total_tokens_used": 450,
        "total_cost_usd": 0.025
    }


# ============================================================================
# Integration Fixtures (combining multiple fixtures)
# ============================================================================

@pytest.fixture
def full_workflow_context(
    sample_loan_application,
    sample_credit_report,
    sample_extracted_document,
    sample_risk_assessment,
    sample_compliance_report,
    sample_lending_decision_approved
) -> Dict[str, Any]:
    """
    Full workflow context with all agent outputs.
    
    Use for end-to-end workflow tests.
    
    Returns:
        Dict[str, Any]: Complete workflow data
    """
    return {
        "loan_application": sample_loan_application,
        "credit_report": sample_credit_report,
        "extracted_documents": [sample_extracted_document],
        "risk_assessment": sample_risk_assessment,
        "compliance_report": sample_compliance_report,
        "lending_decision": sample_lending_decision_approved
    }
