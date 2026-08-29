"""
FastAPI Application - Retail Shelf Monitoring API

This module defines the main FastAPI application for the retail shelf monitoring system.
Implements RESTful API endpoints for two challenges:
- Challenge 1: Out-of-Stock Detection (gap detection on retail shelves)
- Challenge 2: Object Counting (total item counts from shelf images)

Features:
- CORS middleware for cross-origin requests
- API versioning with /api/v1 prefix
- Auto-generated OpenAPI documentation at /docs
- Health check endpoint for monitoring

Architecture:
- Modular routers (health, analysis, detections)
- Dependency injection for database sessions
- Pydantic validation for request/response schemas
- SQLAlchemy ORM for database operations

Related:
- Routers: src/shelf_monitor/api/routers/
- Dependencies: src/shelf_monitor/api/dependencies.py
- Database: src/shelf_monitor/database/
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.shelf_monitor.config.settings import settings

# Create FastAPI application instance with settings
app = FastAPI(
    title=settings.api_title,
    description=(
        "ML-powered API for retail shelf analysis. "
        "Detects out-of-stock gaps and counts objects using YOLOv8."
    ),
    version=settings.api_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/openapi.json",
)

# Configure CORS middleware from settings
# Allows frontend applications to make requests to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # Configurable via .env
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allow all headers
)


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - API welcome message.
    
    Returns basic information about the API and links to documentation.
    
    Returns:
        dict: Welcome message with API metadata
        
    Example:
        >>> GET /
        {
            "message": "Retail Shelf Monitoring API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/v1/health"
        }
    """
    return {
        "message": settings.api_title,
        "version": settings.api_version,
        "environment": settings.environment,
        "docs": "/docs",
        "health": "/api/v1/health",
    }


# ============================================================================
# Router Registration
# ============================================================================

from src.shelf_monitor.api.routers import health, analysis

app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(analysis.router, tags=["Analysis"])

# Future routers (T035):
# from src.shelf_monitor.api.routers import detections
# app.include_router(detections.router, prefix="/api/v1", tags=["Detections"])


if __name__ == "__main__":
    import uvicorn
    
    # Run development server with settings from .env
    # For production, use: uvicorn src.shelf_monitor.api.main:app --host 0.0.0.0 --port 8000
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,  # Auto-reload from settings
        log_level=settings.log_level.lower(),
    )
