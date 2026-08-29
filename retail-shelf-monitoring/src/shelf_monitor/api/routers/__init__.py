"""
API Routers Package

This package contains FastAPI routers for different API endpoints:
- health: Health check and monitoring endpoints
- analysis: Image analysis and processing endpoints (Challenge 1 & 2)
- detections: Detection results and history endpoints

Routers are registered in main.py with /api/v1 prefix.
"""

from . import health

__all__ = ["health"]
