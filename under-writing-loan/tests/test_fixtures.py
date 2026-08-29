"""
Test suite for pytest fixtures.

Validates that all fixtures in conftest.py work correctly and provide
valid data for agent testing.

Task: T014 - Validate pytest fixtures
"""

import pytest
from decimal import Decimal
from datetime import datetime
from pathlib import Path


# ============================================================================
# Pydantic Model Fixture Tests
# ============================================================================

def test_sample_loan_application(sample_loan_application):
    """Validate sample loan application fixture."""
    assert sample_loan_application.application_id == "APP-2025-001"
    assert sample_loan_application.first_name == "Jane"
    assert sample_loan_application.last_name == "Doe"
    assert len(sample_loan_application.document_paths) >= 1
    assert sample_loan_application.requested_amount > 0


def test_sample_loan_application_poor_credit(sample_loan_application_poor_credit):
    """Validate poor credit loan application fixture."""
    assert sample_loan_application_poor_credit.application_id == "APP-2025-002"
    assert sample_loan_application_poor_credit.requested_amount > 0


def test_sample_extracted_document(sample_extracted_document):
    """Validate extracted document fixture."""
    assert sample_extracted_document.document_id.startswith("DOC-")
    assert sample_extracted_document.document_type == "pay_stub"
    assert sample_extracted_document.is_valid is True
    assert "structured_data" in sample_extracted_document.model_dump()
    assert sample_extracted_document.confidence_score > 0.5


def test_sample_credit_report(sample_credit_report):
    """Validate credit report fixture (excellent profile)."""
    assert sample_credit_report.credit_score == 780
    assert sample_credit_report.payment_history == "excellent"
    assert sample_credit_report.derogatory_marks == 0


def test_sample_credit_report_poor(sample_credit_report_poor):
    """Validate poor credit report fixture."""
    assert sample_credit_report_poor.credit_score == 590
    assert sample_credit_report_poor.payment_history == "poor"
    assert sample_credit_report_poor.derogatory_marks > 0


def test_sample_risk_assessment(sample_risk_assessment):
    """Validate risk assessment fixture."""
    assert sample_risk_assessment.risk_level in ["low", "medium", "high"]
    assert sample_risk_assessment.risk_score >= 0.0
    assert sample_risk_assessment.risk_score <= 100.0
    assert sample_risk_assessment.recommendation in ["approve", "review", "deny"]
    assert len(sample_risk_assessment.reasoning) >= 50


def test_sample_compliance_report(sample_compliance_report):
    """Validate compliance report fixture."""
    assert isinstance(sample_compliance_report.is_compliant, bool)
    assert sample_compliance_report.compliance_score >= 0.0
    assert sample_compliance_report.compliance_score <= 100.0
    assert len(sample_compliance_report.policies_evaluated) > 0
    assert sample_compliance_report.rag_chunks_used >= 0


def test_sample_lending_decision_approved(sample_lending_decision_approved):
    """Validate approved lending decision fixture."""
    assert sample_lending_decision_approved.decision in ["approved", "conditional_approval", "denied", "refer_to_manual"]
    assert sample_lending_decision_approved.decision_confidence >= 0.0
    assert sample_lending_decision_approved.decision_confidence <= 1.0
    assert len(sample_lending_decision_approved.decision_summary) >= 100


def test_sample_lending_decision_rejected(sample_lending_decision_rejected):
    """Validate rejected lending decision fixture."""
    assert sample_lending_decision_rejected.decision == "denied"
    assert len(sample_lending_decision_rejected.denial_reasons) > 0
    assert sample_lending_decision_rejected.approved_amount is None


def test_sample_policy_document(sample_policy_document):
    """Validate policy document fixture."""
    assert sample_policy_document.chunk_id.startswith("POL-")
    assert len(sample_policy_document.content) >= 50
    assert sample_policy_document.chunk_index >= 0
    assert sample_policy_document.total_chunks > 0


# ============================================================================
# Mock Azure Client Tests
# ============================================================================

def test_mock_azure_openai_client(mock_azure_openai_client):
    """Validate mock Azure OpenAI client."""
    response = mock_azure_openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "test"}]
    )
    
    assert response.choices[0].message.content is not None
    assert response.usage.total_tokens > 0


def test_mock_document_intelligence_client(mock_document_intelligence_client):
    """Validate mock Document Intelligence client."""
    result = mock_document_intelligence_client.begin_analyze_document(
        "prebuilt-document",
        document="test.pdf"
    ).result()
    
    assert result.content is not None
    assert result.confidence > 0


def test_mock_search_client(mock_search_client):
    """Validate mock AI Search client."""
    results = mock_search_client.search(search_text="DTI requirements")
    
    assert len(results) > 0
    assert "chunk_id" in results[0]


# ============================================================================
# File System Fixture Tests
# ============================================================================

def test_temp_data_dir(temp_data_dir):
    """Validate temporary directory fixture."""
    assert temp_data_dir.exists()
    assert temp_data_dir.is_dir()
    
    # Create a test file
    test_file = temp_data_dir / "test.txt"
    test_file.write_text("test content")
    assert test_file.exists()


def test_sample_pdf_path(sample_pdf_path):
    """Validate sample PDF fixture."""
    assert sample_pdf_path.exists()
    assert sample_pdf_path.suffix == ".pdf"
    assert sample_pdf_path.stat().st_size > 0


def test_mock_uploaded_documents(mock_uploaded_documents):
    """Validate mock uploaded documents fixture."""
    assert len(mock_uploaded_documents) >= 3
    assert all(doc.exists() for doc in mock_uploaded_documents)
    assert all(doc.suffix == ".pdf" for doc in mock_uploaded_documents)
    
    # Check that at least one is a paystub
    file_names = [doc.name for doc in mock_uploaded_documents]
    assert any("paystub" in name.lower() for name in file_names)


# ============================================================================
# Database Fixture Tests
# ============================================================================

def test_mock_credit_db_connection(mock_credit_db_connection):
    """Validate mock credit database connection."""
    cursor = mock_credit_db_connection.cursor()
    cursor.fetchone()
    
    # Just verify it's callable and doesn't error
    assert cursor.fetchone is not None


def test_mock_application_db_connection(mock_application_db_connection):
    """Validate mock application database connection."""
    cursor = mock_application_db_connection.cursor()
    cursor.fetchone()
    
    # Just verify it's callable and doesn't error
    assert cursor.fetchone is not None


# ============================================================================
# Configuration Fixture Tests
# ============================================================================

def test_mock_env_vars(mock_env_vars):
    """Validate environment variables fixture."""
    import os
    
    # Check that Azure OpenAI endpoint is set
    assert os.getenv("AZURE_OPENAI_ENDPOINT") is not None
    assert "mock" in os.getenv("AZURE_OPENAI_ENDPOINT")
    
    # Check that API key is set
    assert os.getenv("AZURE_OPENAI_KEY") is not None


def test_sample_application_state(sample_application_state):
    """Validate application state fixture."""
    assert sample_application_state["application_id"] == "APP-2025-001"
    assert "loan_application" in sample_application_state
    assert "current_agent" in sample_application_state
    assert "total_tokens_used" in sample_application_state


# ============================================================================
# Integration Tests (using multiple fixtures)
# ============================================================================

def test_fixtures_integration(
    sample_loan_application,
    sample_credit_report,
    sample_risk_assessment,
    sample_compliance_report,
    sample_lending_decision_approved
):
    """
    Test that fixtures can be used together in workflow.
    
    Validates data consistency across related fixtures.
    """
    # Verify SSNs match
    assert sample_loan_application.ssn == sample_credit_report.ssn
    
    # Verify application IDs match
    assert sample_loan_application.application_id == sample_risk_assessment.application_id
    assert sample_loan_application.application_id == sample_compliance_report.application_id
    assert sample_loan_application.application_id == sample_lending_decision_approved.application_id
    
    # Verify risk level matches in risk assessment and decision
    assert sample_risk_assessment.risk_level == sample_lending_decision_approved.risk_level
    
    # Verify compliance score is consistent
    assert sample_compliance_report.compliance_score == sample_lending_decision_approved.compliance_score
