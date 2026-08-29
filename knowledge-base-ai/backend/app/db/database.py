"""SQLAlchemy 2.0 async engine, session factory, and declarative Base.

Usage
-----
Import the session factory for FastAPI dependency injection::

    from app.db.database import get_async_session

    @router.get("/items")
    async def list_items(session: AsyncSession = Depends(get_async_session)):
        ...

Import ``Base`` in every ORM model module so all tables are registered::

    from app.db.database import Base

    class Document(Base):
        __tablename__ = "documents"
        ...

Call ``init_db()`` once at application startup (inside the FastAPI lifespan
context manager in ``app.main``) to create all tables that do not yet exist.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy ORM models.

    All model modules must import and inherit from this class so that
    ``Base.metadata.create_all()`` discovers their tables.
    """


# ---------------------------------------------------------------------------
# Engine — created lazily on first call to ensure settings are loaded
# ---------------------------------------------------------------------------
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    global _engine  # noqa: PLW0603
    if _engine is None:
        db_url = settings.database_url
        connect_args: dict[str, object] = {}

        if settings.is_sqlite:
            # Required for SQLite to allow use across async tasks.
            # timeout=30: wait up to 30 s for write-lock to be released (prevents
            # "database is locked" errors under concurrent async requests).
            connect_args["check_same_thread"] = False
            connect_args["timeout"] = 30

        _engine = create_async_engine(
            db_url,
            echo=settings.log_level == "DEBUG",
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        log.info("database_engine_created", url=_sanitise_url(db_url))
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory  # noqa: PLW0603
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """Create all tables defined on ``Base.metadata`` if they do not exist.

    Call once in the FastAPI ``lifespan`` startup handler.  Idempotent — safe
    to call on every startup (no-op when tables already exist).
    """
    # Importing models here ensures their classes are registered on Base.metadata
    # before create_all() is executed.  The imports look unused but are essential.
    import app.models.document  # noqa: F401
    import app.models.conversation  # noqa: F401
    import app.models.message  # noqa: F401
    import app.models.document_summary  # noqa: F401
    import app.models.ingestion_job  # noqa: F401

    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    log.info("database_tables_initialised", table_count=len(Base.metadata.tables))


async def close_db() -> None:
    """Dispose the connection pool.  Call in the FastAPI ``lifespan`` shutdown."""
    global _engine  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
        log.info("database_engine_disposed")
        _engine = None


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that provides a database session.

    Commits on success, rolls back on exception, and always closes the
    session.  Prefer using ``get_async_session`` as a FastAPI ``Depends``
    dependency for request-scoped sessions.

    Example::

        async with get_session() as session:
            result = await session.execute(select(Document))
    """
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an ``AsyncSession``.

    Use with ``Depends``::

        from fastapi import Depends
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.db.database import get_async_session

        @router.get("/documents")
        async def list_docs(db: AsyncSession = Depends(get_async_session)):
            ...
    """
    async with get_session() as session:
        yield session


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _sanitise_url(url: str) -> str:
    """Redact password from database URL for safe logging."""
    if "@" in url and "://" in url:
        scheme_rest = url.split("://", 1)
        if len(scheme_rest) == 2:
            scheme, rest = scheme_rest
            if "@" in rest:
                creds, host_db = rest.rsplit("@", 1)
                user = creds.split(":")[0]
                return f"{scheme}://{user}:***@{host_db}"
    return url
