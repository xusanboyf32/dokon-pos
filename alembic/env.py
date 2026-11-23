"""Alembic muhiti (async).

- Baza manzili alembic.ini dan emas, ilova sozlamalaridan (.env) olinadi —
  manzil va parol bitta joyda saqlanadi.
- `target_metadata` — barcha modellar; autogenerate shu bilan bazani solishtiradi.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import app.core.model_registry  # noqa: F401 — barcha modellarni metadata'ga ro'yxatdan o'tkazadi
from alembic import context
from app.core.config import get_settings
from app.core.database import Base

config = context.config
config.set_main_option("sqlalchemy.url", str(get_settings().database_url))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """SQL'ni bazaga ulanmasdan faylga chiqarish (alembic upgrade head --sql)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,  # ustun turi o'zgarsa ham (String(50) → String(100)) aniqlaydi
        compare_server_default=True,  # default qiymat o'zgarishini ham aniqlaydi
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
