"""Async Alembic environment. DATABASE_URL is required; credentials stay outside source."""
import asyncio
import os
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
config = context.config
url = os.getenv("DATABASE_URL", "")
if not url.startswith("postgresql+asyncpg://"):
    raise RuntimeError("DATABASE_URL must use postgresql+asyncpg")


def offline():
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def migrate(connection):
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def online():
    options = {"sqlalchemy.url": url}
    engine = async_engine_from_config(options, prefix="sqlalchemy.", poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    offline()
else:
    asyncio.run(online())
