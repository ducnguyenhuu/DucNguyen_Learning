"""
Credit router - handles credit report queries.

Provides endpoints for retrieving mock credit bureau data.
In production, this would integrate with real credit bureau APIs.
"""

import logging
import re
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from ..config import CREDIT_DB
from ..database import get_db_connection
from ..models import CreditReportResponse, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/credit/{ssn}",
    response_model=CreditReportResponse,
    responses={
        200: {"description": "Credit report retrieved successfully"},
        404: {"model": ErrorResponse, "description": "No credit record found"},
        400: {"model": ErrorResponse, "description": "Invalid SSN format"}
    },
    summary="Retrieve credit report for applicant"
)
async def get_credit_report(ssn: str):
    """
    Retrieve mock credit bureau data for given SSN.
    
    Educational note: In production, this would call real credit bureau APIs
    (Experian, Equifax, TransUnion) with proper authentication and compliance.
    
    Args:
        ssn: Social Security Number (XXX-XX-XXXX format)
    
    Returns:
        CreditReportResponse with credit data
    
    Raises:
        HTTPException 400: Invalid SSN format
        HTTPException 404: No credit record found
    """
    # Validate SSN format
    if not re.match(r'^\d{3}-\d{2}-\d{4}$', ssn):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid SSN format",
                "detail": "SSN must match pattern XXX-XX-XXXX",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    try:
        conn = get_db_connection(CREDIT_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT ssn, credit_score, credit_utilization, accounts_open,
                   derogatory_marks, credit_age_months, payment_history,
                   late_payments_12mo, hard_inquiries_12mo
            FROM credit_reports
            WHERE ssn = ?
        """, (ssn,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Credit record not found",
                    "detail": f"No credit report exists for SSN {ssn}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        logger.info(f"Retrieved credit report for SSN: {ssn}")
        
        return CreditReportResponse(
            ssn=row["ssn"],
            report_date=datetime.utcnow().isoformat(),
            credit_score=row["credit_score"],
            credit_utilization=row["credit_utilization"],
            accounts_open=row["accounts_open"],
            derogatory_marks=row["derogatory_marks"],
            credit_age_months=row["credit_age_months"],
            payment_history=row["payment_history"],
            late_payments_12mo=row["late_payments_12mo"],
            hard_inquiries_12mo=row["hard_inquiries_12mo"],
            bureau_source="mock_credit_bureau"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving credit report for {ssn}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "detail": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
