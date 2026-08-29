"""
Health Check Router - System Health Monitoring

This router provides health check endpoints to monitor system status:
- Application status (running/degraded/down)
- Database connectivity
- Model availability (future)
- External service status (future)

Endpoints:
    GET /api/v1/health - Basic health check
    GET /api/v1/health/db - Database connectivity check
    GET /api/v1/health/ready - Kubernetes readiness probe

Usage:
    # Import in main.py
    from src.shelf_monitor.api.routers import health
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    
    # Test endpoints
    curl http://localhost:8000/api/v1/health
    curl http://localhost:8000/api/v1/health/db

Related:
- API main: src/shelf_monitor/api/main.py
- Database: src/shelf_monitor/database/session.py
- Dependencies: src/shelf_monitor/api/dependencies.py
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.shelf_monitor.api.dependencies import get_db

# Create router with prefix and tags
router = APIRouter()


@router.get("/health", summary="Basic health check")
async def health_check():
    """
    Basic health check endpoint.
    
    Returns application status without checking dependencies.
    Use this for basic uptime monitoring.
    
    Returns:
        dict: Health status with application metadata
        
    Example Response:
        {
            "status": "healthy",
            "service": "Retail Shelf Monitoring API",
            "version": "1.0.0"
        }
    """
    return {
        "status": "healthy",
        "service": "Retail Shelf Monitoring API",
        "version": "1.0.0"
    }


@router.get("/health/db", summary="Database health check")
async def health_check_db(db: Session = Depends(get_db)):
    """
    Database connectivity health check.
    
    Tests database connection by executing a simple query.
    Returns 200 if database is accessible, 503 if connection fails.
    
    Args:
        db: Database session (injected by FastAPI)
        
    Returns:
        dict: Health status with database connectivity info
        
    Raises:
        HTTPException: 503 if database connection fails
        
    Example Response:
        {
            "status": "healthy",
            "database": "connected",
            "service": "Retail Shelf Monitoring API"
        }
    """
    try:
        # Execute simple query to test connection
        # Using SQLAlchemy 2.0 text() for raw SQL
        db.execute(text("SELECT 1"))
        
        return {
            "status": "healthy",
            "database": "connected",
            "service": "Retail Shelf Monitoring API"
        }
    except Exception as e:
        # Database connection failed
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "service": "Retail Shelf Monitoring API"
            }
        )


@router.get("/health/ready", summary="Readiness probe")
async def health_ready(db: Session = Depends(get_db)):
    """
    Kubernetes readiness probe endpoint.
    
    Checks if application is ready to serve traffic:
    - Database connection is active
    - Critical dependencies are available
    
    Use this for Kubernetes readiness probes to prevent traffic
    routing to unhealthy pods.
    
    Args:
        db: Database session (injected by FastAPI)
        
    Returns:
        dict: Readiness status
        
    Raises:
        HTTPException: 503 if application is not ready
        
    Example Response:
        {
            "status": "ready",
            "database": "connected",
            "models": "loaded"
        }
    """
    try:
        # Check database connection
        db.execute(text("SELECT 1"))
        
        # Future checks can be added here:
        # - Check if YOLO model file exists
        # - Check if required directories are accessible
        # - Check external service availability
        
        return {
            "status": "ready",
            "database": "connected",
            "models": "pending"  # Will be "loaded" after T028-T030
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "error": str(e)
            }
        )
