"""
Health router - handles health check and monitoring.

Provides endpoints for checking server and database health.
Critical for monitoring and load balancer health checks.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from ..config import CREDIT_DB, APP_DB, SERVER_VERSION
from ..database import check_database_health
from ..models import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        200: {"description": "Server is healthy"},
        503: {"description": "Server is unhealthy"}
    },
    summary="Health check endpoint"
)
async def health_check():
    """
    Check server health and database connectivity.
    
    Used by:
    - Monitoring systems to detect outages
    - Load balancers for health checks
    - Startup validation in notebooks
    
    Returns:
        HealthResponse with status and database health
        
    Status codes:
        - 200: All systems operational
        - 503: One or more databases unavailable
    """
    credit_db_healthy = check_database_health(CREDIT_DB)
    app_db_healthy = check_database_health(APP_DB)
    
    is_healthy = credit_db_healthy and app_db_healthy
    
    response = HealthResponse(
        status="healthy" if is_healthy else "degraded",
        version=SERVER_VERSION,
        timestamp=datetime.utcnow().isoformat(),
        database={
            "credit_bureau": credit_db_healthy,
            "application_db": app_db_healthy
        }
    )
    
    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    
    if not is_healthy:
        logger.warning(f"Health check degraded: credit_db={credit_db_healthy}, app_db={app_db_healthy}")
    
    return JSONResponse(content=response.dict(), status_code=status_code)
