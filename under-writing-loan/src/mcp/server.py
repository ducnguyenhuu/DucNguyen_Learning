"""
FastAPI MCP (Model Context Protocol) Server - Main Application.

This is the main entry point for the MCP server. It follows production-grade
FastAPI project structure with separation of concerns:

Structure:
    server.py           - Main app (this file) - FastAPI setup and router registration
    config.py           - Configuration constants and paths
    models.py           - Pydantic request/response models
    database.py         - Database connection helpers
    routers/            - API endpoint routers grouped by domain
        ├── files.py        - Document file access
        ├── credit.py       - Credit report queries  
        ├── applications.py - Application metadata CRUD
        ├── admin.py        - Administrative endpoints
        └── health.py       - Health checks

Benefits of this structure:
    - Each router can be developed and tested independently
    - Models are reusable across routers
    - Easy to add new endpoints without modifying existing code
    - Configuration changes don't require touching business logic
    - Clear separation makes code easier to understand and maintain

Usage:
    # Start server
    uvicorn src.mcp.server:app --reload --port 8000
    
    # Or with the startup script
    bash src/mcp/run_server.sh

API Documentation (when server is running):
    - Interactive docs: http://localhost:8000/docs
    - OpenAPI spec: http://localhost:8000/openapi.json
"""

import logging

from fastapi import FastAPI

# Import configuration
from .config import (
    SERVER_TITLE, SERVER_DESCRIPTION, SERVER_VERSION,
    UPLOAD_DIR, CREDIT_DB, APP_DB
)

# Import routers
from .routers import files, credit, applications, admin, health

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Initialize FastAPI Application
# ============================================================================

app = FastAPI(
    title=SERVER_TITLE,
    description=SERVER_DESCRIPTION,
    version=SERVER_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# ============================================================================
# Register Routers (API Endpoints)
# ============================================================================
# Each router handles a specific domain of the API.
# This keeps the code organized and allows independent development.

app.include_router(
    files.router,
    tags=["Files"],
    responses={404: {"description": "File not found"}}
)

app.include_router(
    credit.router,
    tags=["Credit"],
    responses={404: {"description": "Credit record not found"}}
)

app.include_router(
    applications.router,
    tags=["Applications"],
    responses={404: {"description": "Application not found"}}
)

app.include_router(
    admin.router,
    tags=["Admin"],
    responses={500: {"description": "Operation failed"}}
)

app.include_router(
    health.router,
    tags=["Health"]
)



# ============================================================================
# Lifecycle Events
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Log server startup and configuration.
    
    This runs once when the server starts. Useful for:
    - Validating configuration
    - Establishing database connections
    - Loading ML models
    - Printing helpful information
    """
    logger.info("=" * 80)
    logger.info("MCP Server Starting")
    logger.info("=" * 80)
    logger.info(f"Version: {SERVER_VERSION}")
    logger.info(f"Upload Directory: {UPLOAD_DIR}")
    logger.info(f"Credit DB: {CREDIT_DB} (exists: {CREDIT_DB.exists()})")
    logger.info(f"Application DB: {APP_DB} (exists: {APP_DB.exists()})")
    logger.info("=" * 80)
    logger.info("API Documentation: http://localhost:8000/docs")
    logger.info("Health Check: http://localhost:8000/health")
    logger.info("=" * 80)
    logger.info(f"Registered {len(app.routes)} routes")
    logger.info("=" * 80)


@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup on server shutdown.
    
    This runs once when the server stops. Useful for:
    - Closing database connections
    - Flushing logs
    - Cleaning up temporary files
    """
    logger.info("MCP Server Shutting Down")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    """
    Run the server directly with: python -m src.mcp.server
    
    For development, it's better to use:
        uvicorn src.mcp.server:app --reload --port 8000
    
    The --reload flag automatically restarts the server when code changes.
    """
    import uvicorn
    from .config import SERVER_HOST, SERVER_PORT
    
    uvicorn.run(
        "src.mcp.server:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,
        log_level="info"
    )
