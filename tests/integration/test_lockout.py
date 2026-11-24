"""Kirishga urinishdan himoya (A-032): 10 ta ketma-ket xato → blok, faqat admin ochadi."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import Role
from app.modules.accounts.models import UserAccount
from app.modules.auth import repository as auth_repo
from app.modules.auth.exceptions import AccountLockedError, InvalidCredentialsError
from app.modules.auth.service import MAX_FAILED_ATTEMPTS, AuthService
from tests.integration.test_auth_service import CLIENT, PASSWORD, create_user

WRONG = "9999"


async def wrong_login(service: AuthService, username: str = "anvar") -> None:
    await service.login(username, WRONG, **CLIENT)


async def fail_times(service: AuthService, times: int, username: str = "anvar") -> None:
    for _ in range(times):
        with pytest.raises(InvalidCredentialsError):
            await wrong_login(service, username)


async def lock(service: AuthService, username: str = "anvar") -> None:
    """Akkauntni bloklash: 9 ta xato + 10-chisi."""
    await fail_times(service, MAX_FAILED_ATTEMPTS - 1, username)
    with pytest.raises(AccountLockedError):
        await wrong_login(service, username)


def test_threshold_is_ten() -> None:
    assert MAX_FAILED_ATTEMPTS == 10


async def test_nine_failures_do_not_lock(db_session: AsyncSession, service: AuthService) -> None:
    account = await create_user(db_session)

    await fail_times(service, 9)

    await db_session.refresh(account)
    assert (account.failed_attempts, account.locked_at) == (9, None)
    await service.login("anvar", PASSWORD, **CLIENT)  # hali kira oladi


async def test_tenth_failure_locks_with_clear_message(
    db_session: AsyncSession, service: AuthService
) -> None:
    account = await create_user(db_session)

    await fail_times(service, 9)
    with pytest.raises(AccountLockedError) as error:
        await wrong_login(service)

    assert error.value.status_code == 423
    assert error.value.message == "Hisob bloklandi, administratorga murojaat qiling"
    await db_session.refresh(account)
    assert account.locked_at is not None


async def test_correct_password_is_rejected_while_locked(
    db_session: AsyncSession, service: AuthService
) -> None:
    await create_user(db_session)
    await lock(service)

    with pytest.raises(AccountLockedError):
        await service.login("anvar", PASSWORD, **CLIENT)


async def test_lock_has_no_time_limit(db_session: AsyncSession, service: AuthService) -> None:
    """Vaqt o'tsa ham o'zi ochilmaydi — faqat admin (A-032)."""
    account = await create_user(db_session)
    await lock(service)

    await db_session.refresh(account)
    assert account.locked_at is not None  # hech qanday "qachongacha" maydoni yo'q


async def test_successful_login_resets_counter(
    db_session: AsyncSession, service: AuthService
) -> None:
    """Ketma-ket: 5 xato, to'g'ri parol, yana 9 xato — blok bo'lmaydi."""
    account = await create_user(db_session)
    await fail_times(service, 5)
    await service.login("anvar", PASSWORD, **CLIENT)
    await fail_times(service, 9)

    await db_session.refresh(account)
    assert (account.failed_attempts, account.locked_at) == (9, None)


async def test_unknown_username_is_never_locked(
    db_session: AsyncSession, service: AuthService
) -> None:
    """Mavjud bo'lmagan username: har doim "Login yoki parol xato", blok xabari chiqmaydi."""
    await fail_times(service, MAX_FAILED_ATTEMPTS + 5, username="yoq_odam")


async def test_lock_does_not_kill_active_session(
    db_session: AsyncSession, service: AuthService
) -> None:
    """Blok faqat yangi kirishni to'xtatadi — ishlab turgan sessiya davom etadi."""
    await create_user(db_session, role=Role.ADMIN, username="dilnoza")
    working = await service.login("dilnoza", PASSWORD, **CLIENT)

    await lock(service, "dilnoza")

    user = await service.authenticate(working.access_token)
    assert user.role is Role.ADMIN
    await service.refresh(working.refresh_token, **CLIENT)


async def test_counter_is_incremented_atomically_in_database(db_session: AsyncSession) -> None:
    """Hisoblagich SQL'da oshiriladi — parallel urinishlar ham yo'qolmaydi."""
    account: UserAccount = await create_user(db_session)

    first = await auth_repo.register_failed_attempt(db_session, account.id)
    second = await auth_repo.register_failed_attempt(db_session, account.id)

    assert (first, second) == (1, 2)
