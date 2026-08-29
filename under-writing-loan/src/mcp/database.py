"""
Database helper functions for MCP server.

Centralizes database connection logic and health checks.
Makes it easy to swap database implementations or add connection pooling.
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    """
    Create database connection with row factory.
    
    Row factory allows accessing columns by name: row["column_name"]
    instead of by index: row[0]
    
    Args:
        db_path: Path to SQLite database file
    
    Returns:
        sqlite3.Connection with row_factory set
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def check_database_health(db_path: Path) -> bool:
    """
    Check if database is accessible.
    
    Used by health check endpoint to verify database connectivity.
    
    Args:
        db_path: Path to SQLite database file
    
    Returns:
        True if database is accessible, False otherwise
    """
    try:
        if not db_path.exists():
            logger.warning(f"Database file does not exist: {db_path}")
            return False
        
        conn = get_db_connection(db_path)
        conn.execute("SELECT 1")
        conn.close()
        return True
    
    except Exception as e:
        logger.error(f"Database health check failed for {db_path}: {e}")
        return False
