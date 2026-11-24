"""Barcha testlar uchun umumiy fixture'lar.

- `app`        — har test uchun yangi FastAPI ilovasi
- `client`     — shu ilovaga so'rov yuboradigan HTTP klient
- `db_session` — har test o'z tranzaksiyasida; test tugagach hammasi ROLLBACK
                 (testlar bir-biriga ta'sir qilmaydi, baza doim toza qoladi)
"""

import os
import tempfile

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
# Test rasmlari loyiha papkasiga emas, vaqtinchalik papkaga tushadi
os.environ["MEDIA_ROOT"] = tempfile.mkdtemp(prefix="dokon-test-media-")

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
from app.core.database import engine, get_session  # noqa: E402
from app.core.redis import get_redis  # noqa: E402
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


# ------------------------------------------------------------------ API
@pytest.fixture
async def api(
    app: FastAPI, db_session: AsyncSession, redis_client: Redis
) -> AsyncIterator[AsyncClient]:
    """Ilova testning tranzaksiyali sessiyasidan foydalanadi — test oxirida hammasi ROLLBACK."""

    async def _test_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _test_session
    app.dependency_overrides[get_redis] = lambda: redis_client
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ------------------------------------------------------------------ audit uchun aktyor
@pytest.fixture
async def actor_account_id(db_session: AsyncSession) -> int:
    """Servis testlarida "kim qildi" — bazadagi haqiqiy akkaunt bo'lishi shart.

    Audit jurnali `actor_account_id` ni FK bilan tekshiradi (soxta id=0 o'tmaydi).
    Xodim anonimlashtirilgan — hech qaysi ro'yxatda ko'rinmaydi va testlarga xalaqit bermaydi.
    """
    from app.core.time import utcnow
    from app.modules.accounts.models import UserAccount
    from tests.integration.test_employees_table import make_employee
    from tests.integration.test_user_accounts_table import FAKE_HASH

    now = utcnow()
    employee = make_employee(
        role="admin", phone=None, photo_path=None, archived_at=now, anonymized_at=now
    )
    db_session.add(employee)
    await db_session.flush()
    account = UserAccount(
        employee_id=employee.id, username="audit_actor", password_hash=FAKE_HASH, deleted_at=now
    )
    db_session.add(account)
    await db_session.flush()
    return account.id
