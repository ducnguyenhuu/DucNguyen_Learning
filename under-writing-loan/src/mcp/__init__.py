"""
Model Context Protocol (MCP) server implementation.

This package provides a FastAPI-based MCP server that abstracts access to:
- Uploaded loan application documents (filesystem)
- Mock credit bureau database (SQLite)
- Application metadata storage (SQLite)

The MCP pattern decouples agents from direct data access, providing a clean
API layer that can be replaced with real services in production.

Modules:
- server.py: FastAPI application with MCP endpoints
- create_credit_db.py: Database schema creation script
- seed_data.py: Test data population script
- connectors/: Data source connectors (file, credit, application)

API Specification:
See specs/001-ai-loan-underwriting-system/contracts/mcp-server.yaml

Usage:
    # Start MCP server
    uvicorn src.mcp.server:app --reload --port 8000
    
    # Query credit report
    curl http://localhost:8000/credit/123-45-6789
    
    # Download document
    curl http://localhost:8000/files/app-001/paystub.pdf --output paystub.pdf
"""

__version__ = "1.0.0"
__author__ = "AI Loan Underwriting System"

__all__ = [
    "server",
    "create_credit_db",
    "seed_data",
]
