"""
Applications router - handles application metadata CRUD operations.

Provides endpoints for tracking loan application workflow state.
Stores status, completion flags, costs, and error messages.
"""

import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from ..config import APP_DB
from ..database import get_db_connection
from ..models import ApplicationMetadataResponse, ApplicationUpdateRequest, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/application/{application_id}",
    response_model=ApplicationMetadataResponse,
    responses={
        200: {"description": "Application metadata retrieved successfully"},
        404: {"model": ErrorResponse, "description": "Application not found"}
    },
    summary="Retrieve application metadata"
)
async def get_application(application_id: str):
    """
    Retrieve stored metadata for a loan application.
    
    Args:
        application_id: Unique application identifier
    
    Returns:
        ApplicationMetadataResponse with application data
    
    Raises:
        HTTPException 404: Application not found
    """
    try:
        conn = get_db_connection(APP_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT application_id, status, created_at, updated_at,
                   document_extraction_complete, risk_assessment_complete,
                   compliance_check_complete, decision_complete,
                   final_decision, mlflow_run_id, total_processing_time_seconds,
                   total_cost_usd, error_messages
            FROM applications
            WHERE application_id = ?
        """, (application_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Application not found",
                    "detail": f"No application exists with ID {application_id}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        logger.info(f"Retrieved application metadata for: {application_id}")
        
        # Parse error_messages JSON
        error_messages = json.loads(row["error_messages"]) if row["error_messages"] else []
        
        return ApplicationMetadataResponse(
            application_id=row["application_id"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            document_extraction_complete=bool(row["document_extraction_complete"]),
            risk_assessment_complete=bool(row["risk_assessment_complete"]),
            compliance_check_complete=bool(row["compliance_check_complete"]),
            decision_complete=bool(row["decision_complete"]),
            final_decision=row["final_decision"],
            mlflow_run_id=row["mlflow_run_id"],
            total_processing_time_seconds=row["total_processing_time_seconds"],
            total_cost_usd=row["total_cost_usd"],
            error_messages=error_messages
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving application {application_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "detail": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.put(
    "/application/{application_id}",
    response_model=ApplicationMetadataResponse,
    responses={
        200: {"description": "Application updated successfully"},
        404: {"model": ErrorResponse, "description": "Application not found"},
        400: {"model": ErrorResponse, "description": "Invalid update payload"}
    },
    summary="Update application status and results"
)
async def update_application(application_id: str, update: ApplicationUpdateRequest):
    """
    Update application metadata with processing results.
    
    This endpoint allows agents to persist their results and update workflow state.
    
    Args:
        application_id: Unique application identifier
        update: Fields to update
    
    Returns:
        Updated ApplicationMetadataResponse
    
    Raises:
        HTTPException 404: Application not found
        HTTPException 400: Invalid update payload
    """
    try:
        conn = get_db_connection(APP_DB)
        cursor = conn.cursor()
        
        # Check if application exists
        cursor.execute("SELECT 1 FROM applications WHERE application_id = ?", (application_id,))
        if not cursor.fetchone():
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Application not found",
                    "detail": f"No application exists with ID {application_id}",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        # Build dynamic UPDATE query
        update_fields = []
        update_values = []
        
        if update.status is not None:
            update_fields.append("status = ?")
            update_values.append(update.status)
        
        if update.document_extraction_complete is not None:
            update_fields.append("document_extraction_complete = ?")
            update_values.append(int(update.document_extraction_complete))
        
        if update.risk_assessment_complete is not None:
            update_fields.append("risk_assessment_complete = ?")
            update_values.append(int(update.risk_assessment_complete))
        
        if update.compliance_check_complete is not None:
            update_fields.append("compliance_check_complete = ?")
            update_values.append(int(update.compliance_check_complete))
        
        if update.decision_complete is not None:
            update_fields.append("decision_complete = ?")
            update_values.append(int(update.decision_complete))
        
        if update.final_decision is not None:
            update_fields.append("final_decision = ?")
            update_values.append(update.final_decision)
        
        if update.mlflow_run_id is not None:
            update_fields.append("mlflow_run_id = ?")
            update_values.append(update.mlflow_run_id)
        
        if update.total_processing_time_seconds is not None:
            update_fields.append("total_processing_time_seconds = ?")
            update_values.append(update.total_processing_time_seconds)
        
        if update.total_cost_usd is not None:
            update_fields.append("total_cost_usd = ?")
            update_values.append(update.total_cost_usd)
        
        if update.error_messages is not None:
            update_fields.append("error_messages = ?")
            update_values.append(json.dumps(update.error_messages))
        
        # Always update updated_at
        update_fields.append("updated_at = ?")
        update_values.append(datetime.utcnow().isoformat())
        
        # Execute update
        update_values.append(application_id)
        query = f"UPDATE applications SET {', '.join(update_fields)} WHERE application_id = ?"
        cursor.execute(query, update_values)
        conn.commit()
        conn.close()
        
        logger.info(f"Updated application: {application_id}")
        
        # Return updated application
        return await get_application(application_id)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating application {application_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Internal server error",
                "detail": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
