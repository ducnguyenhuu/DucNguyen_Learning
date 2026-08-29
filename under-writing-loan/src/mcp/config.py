"""
Configuration module for MCP server.

Centralizes all configuration constants, paths, and settings.
Makes it easy to change configuration without modifying business logic.
"""

from pathlib import Path

# Project paths
REPO_ROOT = Path(__file__).parent.parent.parent
UPLOAD_DIR = REPO_ROOT / "data" / "applications"
CREDIT_DB = REPO_ROOT / "data" / "mock_credit_bureau.db"
APP_DB = REPO_ROOT / "data" / "database.db"

# Server configuration
SERVER_TITLE = "MCP Server - Mock Credit Bureau & File Access"
SERVER_DESCRIPTION = "Model Context Protocol server for loan underwriting system"
SERVER_VERSION = "1.0.0"
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

# Ensure directories exist on import
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
