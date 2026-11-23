"""Barcha testlar uchun umumiy fixture'lar.

- `app`        — har test uchun yangi FastAPI ilovasi
- `client`     — shu ilovaga so'rov yuboradigan HTTP klient
- `db_session` — har test o'z tranzaksiyasida; test tugagach hammasi ROLLBACK
                 (testlar bir-biriga ta'sir qilmaydi, baza doim toza qoladi)
"""

import os

from app.core.config import Settings

# ------------------------------------------------------------------ test bazasi
# Ilova (va engine) import qilinishidan OLDIN qaysi bazaga ulanishni belgilaymiz.
# Muhit o'zgaruvchisi .env dagi qiymatdan ustun turadi (pydantic-settings qoidasi).
_settings = Settings()
if _settings.test_database_url is not None:
    os.environ["DATABASE_URL"] = str(_settings.test_database_url)
os.environ["ENVIRONMENT"] = "test"
# Redis: testlar alohida baza raqamida (15) — ishchi ma'lumotlarga tegmaydi
os.environ["REDIS_URL"] = str(_settings.test_redis_url or "redis://localhost:6379/15")

# Xavfsizlik qulfi: testlar jadvallarni o'chirib-qayta quradi.
# Bazaning nomi "_test" bilan tugamasa — testlar umuman ishga tushmaydi.
_db_name = os.environ.get("DATABASE_URL", str(_settings.database_url)).rsplit("/", 1)[-1]
if not _db_name.endswith("_test"):
    raise RuntimeError(
        f"Testlar '{_db_name}' bazasida ishga tushmaydi. "
        ".env ga TEST_DATABASE_URL=...dokon_test qo'shing."
    )

from collections.abc import AsyncIterator, Iterator  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic.config import Config as AlembicConfig  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from redis.asyncio import Redis  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from alembic import command  # noqa: E402
from app.core.database import engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.modules.auth.lockout import LoginGuard  # noqa: E402
from app.modules.auth.service import AuthService  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ ilova
@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # raise_app_exceptions=False: kutilmagan xatoda test yiqilmaydi,
    # balki ilova foydalanuvchiga nima qaytarishini (500) tekshiramiz
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


# ------------------------------------------------------------------ baza
@pytest.fixture(scope="session")
def alembic_config() -> AlembicConfig:
    return AlembicConfig(str(PROJECT_ROOT / "alembic.ini"))


@pytest.fixture(scope="session")
def migrated_database(alembic_config: AlembicConfig) -> Iterator[None]:
    """Test sessiyasi boshida bir marta: barcha migratsiyalar qo'llanadi."""
    command.upgrade(alembic_config, "head")
    yield


@pytest.fixture
async def db_session(migrated_database: None) -> AsyncIterator[AsyncSession]:
    """Har test tashqi tranzaksiya ichida ishlaydi va oxirida ROLLBACK qilinadi.

    `join_transaction_mode="create_savepoint"` — test ichidagi commit()
    haqiqiy commit emas, SAVEPOINT bo'ladi. Shuning uchun service kodidagi
    commit()lar ham test tugagach bekor qilinadi.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


# ------------------------------------------------------------------ redis
@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    """Har test toza Redis bazasi bilan boshlanadi va tugaydi."""
    client = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


@pytest.fixture
def guard(redis_client: Redis) -> LoginGuard:
    return LoginGuard(redis_client)


@pytest.fixture
def service(db_session: AsyncSession, guard: LoginGuard) -> AuthService:
    return AuthService(db_session, guard)
