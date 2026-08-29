"""
Pydantic models for MCP server API requests and responses.

Separating models from business logic makes them reusable and easier to test.
These models define the "contract" between client and server.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class CreditReportResponse(BaseModel):
    """Credit report response model."""
    ssn: str
    report_date: str
    credit_score: int = Field(..., ge=300, le=850)
    credit_utilization: float = Field(..., ge=0.0, le=100.0)
    accounts_open: int = Field(..., ge=0)
    derogatory_marks: int = Field(..., ge=0)
    credit_age_months: int = Field(..., ge=0)
    payment_history: str
    late_payments_12mo: int = Field(default=0, ge=0)
    hard_inquiries_12mo: int = Field(default=0, ge=0)
    bureau_source: str = "mock_credit_bureau"


class ApplicationMetadataResponse(BaseModel):
    """Application metadata response model."""
    application_id: str
    status: str
    created_at: str
    updated_at: str
    document_extraction_complete: bool = False
    risk_assessment_complete: bool = False
    compliance_check_complete: bool = False
    decision_complete: bool = False
    final_decision: Optional[str] = None
    mlflow_run_id: Optional[str] = None
    total_processing_time_seconds: Optional[float] = None
    total_cost_usd: Optional[float] = None
    error_messages: List[str] = []


class ApplicationUpdateRequest(BaseModel):
    """Application update request model."""
    status: Optional[str] = None
    document_extraction_complete: Optional[bool] = None
    risk_assessment_complete: Optional[bool] = None
    compliance_check_complete: Optional[bool] = None
    decision_complete: Optional[bool] = None
    final_decision: Optional[str] = None
    mlflow_run_id: Optional[str] = None
    total_processing_time_seconds: Optional[float] = None
    total_cost_usd: Optional[float] = None
    error_messages: Optional[List[str]] = None


class SeedDatabaseRequest(BaseModel):
    """Seed database request model."""
    reset: bool = Field(default=False, description="Drop existing data before seeding")


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str
    timestamp: str
    database: Dict[str, bool]


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    detail: Optional[str] = None
    timestamp: str
