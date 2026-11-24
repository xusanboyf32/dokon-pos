"""Superadmin'ni yaratish/ochish va username/parol qoidalari."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.roles import Role
from app.core.security import verify_password
from app.core.time import utcnow
from app.modules.accounts.superadmin import create_superadmin, unlock_superadmin
from app.modules.accounts.validation import (
    InvalidPasswordError,
    InvalidUsernameError,
    PasswordMismatchError,
)
from app.modules.auth.service import AuthService


async def test_create_superadmin_and_login(db_session: AsyncSession, service: AuthService) -> None:
    account = await create_superadmin(db_session, "  Xusanboy ", "Kuchli2026", "Kuchli2026")

    assert account.username == "xusanboy"  # kichik harf, bo'sh joysiz
    assert account.is_superadmin
    assert verify_password("Kuchli2026", account.password_hash)
    pair = await service.login("xusanboy", "Kuchli2026", ip=None, user_agent=None)
    assert pair.role is Role.SUPERADMIN


async def test_second_superadmin_is_refused(db_session: AsyncSession) -> None:
    await create_superadmin(db_session, "birinchi", "1234", "1234")

    with pytest.raises(ConflictError) as error:
        await create_superadmin(db_session, "ikkinchi", "1234", "1234")
    assert error.value.code == "SUPERADMIN_EXISTS"


@pytest.mark.parametrize("username", ["ab", "ali vali", "анвар", "a@b", "x" * 51])
async def test_invalid_username_is_refused(db_session: AsyncSession, username: str) -> None:
    with pytest.raises(InvalidUsernameError):
        await create_superadmin(db_session, username, "1234", "1234")


@pytest.mark.parametrize("password", ["123", "x" * 65])
async def test_invalid_password_length_is_refused(db_session: AsyncSession, password: str) -> None:
    with pytest.raises(InvalidPasswordError):
        await create_superadmin(db_session, "xusanboy", password, password)


async def test_password_confirmation_must_match(db_session: AsyncSession) -> None:
    with pytest.raises(PasswordMismatchError):
        await create_superadmin(db_session, "xusanboy", "1234", "1235")


async def test_unlock_superadmin(db_session: AsyncSession) -> None:
    account = await create_superadmin(db_session, "xusanboy", "1234", "1234")
    account.locked_at = utcnow()

    unlocked = await unlock_superadmin(db_session)

    assert unlocked.locked_at is None


async def test_unlock_without_superadmin_fails(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await unlock_superadmin(db_session)
