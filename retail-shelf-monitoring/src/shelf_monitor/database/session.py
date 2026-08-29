"""
Database Session Management: SQLAlchemy engine and session factory.

This module provides database connection and session management for the application:
- Engine creation with SQLite configuration
- SessionLocal factory for creating database sessions
- get_db() dependency for FastAPI dependency injection

Usage:
    # FastAPI dependency injection
    @router.get("/products/")
    def get_products(db: Session = Depends(get_db)):
        products = crud.get_products(db)
        return products
    
    # Direct session usage (scripts, notebooks)
    db = SessionLocal()
    try:
        products = crud.get_products(db)
        print(products)
    finally:
        db.close()

Related:
- Models: src/shelf_monitor/database/models.py
- CRUD: src/shelf_monitor/database/crud.py
- Settings: src/shelf_monitor/config/settings.py (T022)
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.shelf_monitor.config.settings import settings


# ============================================================================
# Database Configuration
# ============================================================================

# Get database URL from settings (loaded from .env file)
# Settings provides type safety, validation, and centralized config
# For testing: Override with Settings(database_url="sqlite:///:memory:")
DATABASE_URL = settings.database_url

# Create SQLAlchemy engine
# connect_args={"check_same_thread": False} is needed for SQLite
# SQLite is single-threaded by default, but FastAPI is async/multi-threaded
# This setting allows SQLite to work with multiple threads (safe for read operations)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=settings.log_sql_queries,  # SQL query logging from settings
)

# Create SessionLocal class for database sessions
# autocommit=False: Requires explicit commit() calls (safer, more control)
# autoflush=False: Prevents automatic flush before queries (more predictable)
# bind=engine: Binds sessions to our database engine
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ============================================================================
# Dependency Injection for FastAPI
# ============================================================================


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session.
    
    This function is used as a dependency in FastAPI route handlers.
    It creates a new database session, yields it to the endpoint,
    and ensures the session is closed after the request completes.
    
    Yields:
        Session: SQLAlchemy database session
    
    Example:
        >>> from fastapi import Depends
        >>> from sqlalchemy.orm import Session
        >>> 
        >>> @router.get("/products/")
        >>> def get_products(db: Session = Depends(get_db)):
        ...     products = crud.get_products(db)
        ...     return products
    
    Notes:
        - Session is automatically closed after request (finally block)
        - Exceptions are propagated (FastAPI handles them)
        - Each request gets a fresh session (no shared state)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Helper Functions
# ============================================================================


def create_tables() -> None:
    """
    Create all database tables defined in models.py.
    
    This is a convenience function for development/testing.
    In production, use Alembic migrations instead (alembic upgrade head).
    
    Example:
        >>> from src.shelf_monitor.database.session import create_tables
        >>> create_tables()  # Creates all tables if they don't exist
    
    Notes:
        - Only creates tables that don't already exist
        - Does NOT modify existing tables (use migrations for that)
        - Import models.py before calling (to register models with Base)
    """
    from src.shelf_monitor.database.models import Base
    
    Base.metadata.create_all(bind=engine)


def drop_tables() -> None:
    """
    Drop all database tables.
    
    **WARNING**: This deletes ALL data! Use only for testing/development.
    
    Example:
        >>> from src.shelf_monitor.database.session import drop_tables
        >>> drop_tables()  # Deletes all tables and data
    
    Notes:
        - Irreversible operation
        - Use with extreme caution
        - Prefer Alembic downgrade for controlled rollbacks
    """
    from src.shelf_monitor.database.models import Base
    
    Base.metadata.drop_all(bind=engine)


def get_session() -> Session:
    """
    Get a database session for use in scripts/notebooks.
    
    Returns a new database session. Caller is responsible for closing.
    
    Returns:
        Session: SQLAlchemy database session
    
    Example:
        >>> from src.shelf_monitor.database.session import get_session
        >>> db = get_session()
        >>> try:
        ...     products = crud.get_products(db)
        ...     print(products)
        ... finally:
        ...     db.close()
    
    Notes:
        - Use get_db() for FastAPI endpoints (automatic cleanup)
        - Use get_session() for scripts/notebooks (manual cleanup)
        - Always close the session when done
    """
    return SessionLocal()
