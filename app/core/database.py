"""PostgreSQL ulanishi (async).

- `engine` — ulanishlar havzasi (pool). Butun ilova uchun bitta.
- `SessionFactory` — har so'rov uchun yangi sessiya yaratadi.
- `Base` — barcha modellar shundan meros oladi.
"""

from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

# Constraint va indekslarga bir xil, oldindan ma'lum nom beriladi.
# Shusiz Alembic migratsiyalarida ularni o'zgartirish/o'chirish qiyin bo'ladi.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Har jadvalga: qachon yaratildi va qachon o'zgartirildi (UTC, baza vaqti bilan)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


_settings = get_settings()

_connect_args = {
    "server_settings": {
        "statement_timeout": str(_settings.db_statement_timeout_ms),
        "timezone": "UTC",
        "application_name": "dokon-pos",
    }
}

if _settings.environment == "test":
    # Testlarda pool yo'q: har test o'z ulanishini ochadi va yopadi.
    # Aks holda bir testning event loop'ida ochilgan ulanish keyingisiga "osilib" qoladi.
    engine = create_async_engine(
        str(_settings.database_url), poolclass=NullPool, connect_args=_connect_args
    )
else:
    engine = create_async_engine(
        str(_settings.database_url),
        pool_size=_settings.db_pool_size,
        max_overflow=_settings.db_max_overflow,
        pool_pre_ping=True,  # uzilgan ulanishni ishlatishdan oldin tekshiradi
        connect_args=_connect_args,
    )

SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: so'rov davomida bitta sessiya, oxirida yopiladi."""
    async with SessionFactory() as session:
        yield session
