"""
API routers package.

Each router handles a specific domain of the API:
- files: Document file access
- credit: Credit report queries
- applications: Application metadata CRUD
- admin: Administrative endpoints
- health: Health check and monitoring
"""

from . import files, credit, applications, admin, health

__all__ = ["files", "credit", "applications", "admin", "health"]
