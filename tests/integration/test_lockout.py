"""Kirishga urinishdan himoya — spetsifikatsiya 7-band, har bir kichik band alohida."""

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import Role
from app.modules.auth.exceptions import (
    AccountLockedError,
    AccountTemporarilyLockedError,
    InvalidCredentialsError,
)
from app.modules.auth.lockout import LockDecision, LoginGuard
from app.modules.auth.service import AuthService
from tests.integration.test_auth_service import CLIENT, PASSWORD, create_user

WRONG = "9999"


async def wrong_login(service: AuthService, username: str = "anvar") -> None:
    await service.login(username, WRONG, **CLIENT)


async def fail_times(service: AuthService, times: int, username: str = "anvar") -> None:
    for _ in range(times):
        with pytest.raises(InvalidCredentialsError):
            await wrong_login(service, username)


async def end_temporary_block(redis_client: Redis, username: str = "anvar") -> None:
    """10 daqiqa kutmaslik uchun: blok kalitini o'chiramiz (TTL tugagandek)."""
    await redis_client.delete(f"auth:lock:{username}")


# ================================================================== 7a
async def test_five_wrong_passwords_lock_for_ten_minutes(
    db_session: AsyncSession, service: AuthService, redis_client: Redis
) -> None:
    await create_user(db_session)
    await fail_times(service, 4)

    with pytest.raises(AccountTemporarilyLockedError) as error:
        await wrong_login(service)  # 5-chi xato

    assert error.value.status_code == 423
    assert error.value.message == "Hisob vaqtincha bloklandi, 10 daqiqadan keyin urinib ko'ring"
    assert 590 < await redis_client.ttl("auth:lock:anvar") <= 600


async def test_correct_password_is_rejected_during_temporary_block(
    db_session: AsyncSession, service: AuthService
) -> None:
    await create_user(db_session)
    await fail_times(service, 4)
    with pytest.raises(AccountTemporarilyLockedError):
        await wrong_login(service)

    with pytest.raises(AccountTemporarilyLockedError):
        await service.login("anvar", PASSWORD, **CLIENT)


async def test_attempts_during_block_do_not_extend_it(
    db_session: AsyncSession, service: AuthService, redis_client: Redis
) -> None:
    await create_user(db_session)
    await fail_times(service, 4)
    with pytest.raises(AccountTemporarilyLockedError):
        await wrong_login(service)
    await redis_client.expire("auth:lock:anvar", 100)  # blokdan 500 soniya o'tdi

    for _ in range(10):
        with pytest.raises(AccountTemporarilyLockedError):
            await wrong_login(service)

    assert await redis_client.ttl("auth:lock:anvar") <= 100  # uzaymadi


async def test_rate_limit_counts_even_successful_attempts(guard: LoginGuard) -> None:
    for _ in range(5):
        assert (await guard.on_attempt("anvar")).decision is LockDecision.NONE

    assert (await guard.on_attempt("anvar")).decision is LockDecision.TEMPORARY  # 6-chi


# ================================================================== 7b
async def test_three_failures_after_block_lock_permanently(
    db_session: AsyncSession, service: AuthService, redis_client: Redis
) -> None:
    account = await create_user(db_session)
    await fail_times(service, 4)
    with pytest.raises(AccountTemporarilyLockedError):
        await wrong_login(service)
    await end_temporary_block(redis_client)

    await fail_times(service, 2)
    with pytest.raises(AccountLockedError) as error:
        await wrong_login(service)  # sinov davridagi 3-chi xato

    assert error.value.message == "Hisob bloklandi, administratorga murojaat qiling"
    assert account.locked_at is not None  # doimiy blok BAZADA


async def test_permanent_block_survives_redis_restart(
    db_session: AsyncSession, service: AuthService, redis_client: Redis
) -> None:
    account = await create_user(db_session)
    await fail_times(service, 4)
    with pytest.raises(AccountTemporarilyLockedError):
        await wrong_login(service)
    await end_temporary_block(redis_client)
    await fail_times(service, 2)
    with pytest.raises(AccountLockedError):
        await wrong_login(service)

    await redis_client.flushdb()  # Redis qayta ishga tushdi, xotira tozalandi

    with pytest.raises(AccountLockedError):
        await service.login("anvar", PASSWORD, **CLIENT)
    assert account.locked_at is not None


async def test_unknown_username_never_reveals_itself(
    service: AuthService, redis_client: Redis
) -> None:
    """Mavjud bo'lmagan username ham xuddi shunday bloklanadi — farqi bilinmaydi."""
    await fail_times(service, 4, username="yoq_odam")
    with pytest.raises(AccountTemporarilyLockedError):
        await wrong_login(service, "yoq_odam")
    await end_temporary_block(redis_client, "yoq_odam")
    await fail_times(service, 2, username="yoq_odam")

    # "Doimiy" blok bazaga yozilolmaydi — yana vaqtincha blok (xabar ham shunday)
    with pytest.raises(AccountTemporarilyLockedError):
        await wrong_login(service, "yoq_odam")


# ================================================================== 7c
async def test_successful_login_resets_counters(
    db_session: AsyncSession, service: AuthService, redis_client: Redis
) -> None:
    await create_user(db_session)
    await fail_times(service, 4)

    await service.login("anvar", PASSWORD, **CLIENT)

    assert await redis_client.keys("auth:*") == []
    await fail_times(service, 4)  # yana 4 ta xato — blok yo'q


# ================================================================== 7g
async def test_permanent_block_does_not_kill_active_session(
    db_session: AsyncSession, service: AuthService, redis_client: Redis
) -> None:
    await create_user(db_session, role=Role.ADMIN, username="dilnoza")
    working = await service.login("dilnoza", PASSWORD, **CLIENT)  # ishlab turibdi

    await fail_times(service, 4, username="dilnoza")
    with pytest.raises(AccountTemporarilyLockedError):
        await wrong_login(service, "dilnoza")
    await end_temporary_block(redis_client, "dilnoza")
    await fail_times(service, 2, username="dilnoza")
    with pytest.raises(AccountLockedError):
        await wrong_login(service, "dilnoza")

    user = await service.authenticate(working.access_token)  # sessiya davom etadi
    assert user.role is Role.ADMIN
    await service.refresh(working.refresh_token, **CLIENT)


# ================================================================== fail-open
async def test_redis_down_does_not_stop_the_shop(db_session: AsyncSession) -> None:
    """Redis ishlamasa — himoya vaqtincha o'chadi, lekin login ishlaydi (A-variant)."""
    dead_redis = Redis.from_url("redis://localhost:1/0", socket_connect_timeout=0.2)
    service = AuthService(db_session, LoginGuard(dead_redis))
    await create_user(db_session)

    for _ in range(10):  # cheksiz xato — blok yo'q, chunki hisoblagich yo'q
        with pytest.raises(InvalidCredentialsError):
            await wrong_login(service)
    pair = await service.login("anvar", PASSWORD, **CLIENT)

    assert pair.access_token
    await dead_redis.aclose()
