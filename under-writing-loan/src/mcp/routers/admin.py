"""
Admin router - handles administrative operations.

Provides endpoints for database seeding and other admin tasks.
In production, these would be protected with authentication.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from ..config import CREDIT_DB, REPO_ROOT
from ..database import get_db_connection
from ..models import SeedDatabaseRequest, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/admin/seed_credit_db",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Database seeded successfully"},
        500: {"model": ErrorResponse, "description": "Database seeding failed"}
    },
    summary="Seed mock credit bureau database"
)
async def seed_credit_database(request: SeedDatabaseRequest = SeedDatabaseRequest()):
    """
    Populate mock credit bureau database with test profiles.
    
    Creates 4 test profiles with different credit characteristics:
    - Excellent credit (780+ score)
    - Good credit (720 score)
    - Fair credit (670 score)
    - Poor credit (590 score)
    
    Args:
        request: Optional configuration (reset=True to drop existing data)
    
    Returns:
        Success message with profile count and details
    
    Raises:
        HTTPException 500: Database seeding failed
    """
    try:
        # Import seed_data module
        import sys
        sys.path.insert(0, str(REPO_ROOT))
        from src.mcp.seed_data import seed_credit_database as seed_func
        
        # Call seeding function
        profiles_created = seed_func(reset=request.reset)
        
        # Query created profiles for response
        conn = get_db_connection(CREDIT_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT ssn, name, credit_score FROM credit_reports ORDER BY credit_score DESC")
        profiles = [
            {"ssn": row["ssn"], "name": row["name"], "credit_score": row["credit_score"]}
            for row in cursor.fetchall()
        ]
        conn.close()
        
        logger.info(f"Successfully seeded {profiles_created} credit profiles")
        
        return {
            "message": f"Successfully seeded {profiles_created} credit profiles",
            "profiles": profiles,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error seeding credit database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Database seeding failed",
                "detail": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
