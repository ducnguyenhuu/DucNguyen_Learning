"""Alembic async environment configuration.

Uses SQLAlchemy 2.0 async engine so migrations run with the same database
driver (aiosqlite / asyncpg) as the application.

The database URL is read from ``settings.database_url`` at migration time so
there is a single source of truth (the ``.env`` file).  Alembic's own
``sqlalchemy.url`` in ``alembic.ini`` is intentionally left blank.
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Load application config and models before Alembic inspects metadata
# ---------------------------------------------------------------------------
from app.config import settings  # noqa: E402

# Import all ORM models so their table definitions are registered on Base.metadata
import app.models.document  # noqa: F401, E402
import app.models.conversation  # noqa: F401, E402
import app.models.message  # noqa: F401, E402
import app.models.document_summary  # noqa: F401, E402
import app.models.ingestion_job  # noqa: F401, E402
from app.db.database import Base  # noqa: E402

# ---------------------------------------------------------------------------
# Alembic Config object and logging setup
# ---------------------------------------------------------------------------
config = context.config

# Inject the application DATABASE_URL so alembic.ini doesn't need one
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Migration helpers
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a live DB connection).

    Useful for generating SQL scripts to review or apply manually.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations against a live database using the async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live database connection)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
