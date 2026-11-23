"""AuthService: login, refresh (rotation + o'g'irlikni aniqlash), logout, authenticate."""

from datetime import timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.roles import Role
from app.core.security import decode_access_token, hash_password, hash_refresh_token
from app.core.time import utcnow
from app.modules.accounts.models import UserAccount
from app.modules.auth.exceptions import (
    AccountLockedError,
    InvalidCredentialsError,
    RefreshTokenReusedError,
    SessionExpiredError,
    SessionInvalidError,
)
from app.modules.auth.models import AuthSession, RevokeReason
from app.modules.auth.service import AuthService, TokenPair
from app.modules.employees.models import Employee
from tests.integration.test_employees_table import make_employee

PASSWORD = "1234"
CLIENT = {"ip": "192.168.1.10", "user_agent": "pytest"}


async def create_user(
    session: AsyncSession,
    *,
    username: str = "anvar",
    role: Role = Role.KASSIR,
    phone: str = "+998901234567",
) -> UserAccount:
    employee = make_employee(role=role.value, phone=phone)
    session.add(employee)
    await session.flush()
    account = UserAccount(
        employee_id=employee.id, username=username, password_hash=hash_password(PASSWORD)
    )
    session.add(account)
    await session.flush()
    return account


async def sessions_of(session: AsyncSession, account_id: int) -> list[AuthSession]:
    stmt = select(AuthSession).where(AuthSession.account_id == account_id)
    result = await session.execute(stmt.execution_options(populate_existing=True))
    return list(result.scalars())


async def login(session: AsyncSession, username: str = "anvar") -> TokenPair:
    return await AuthService(session).login(username, PASSWORD, **CLIENT)


# ================================================================== login
async def test_login_success_creates_session_and_tokens(db_session: AsyncSession) -> None:
    account = await create_user(db_session)

    pair = await login(db_session)

    assert pair.role is Role.KASSIR
    claims = decode_access_token(pair.access_token)
    assert claims.account_id == account.id
    [auth_session] = await sessions_of(db_session, account.id)
    assert claims.session_id == auth_session.id
    assert auth_session.refresh_token_hash == hash_refresh_token(pair.refresh_token)
    assert auth_session.ip == "192.168.1.10"
    # 24 soat (A-005)
    lifetime = auth_session.absolute_expires_at - auth_session.created_at
    assert timedelta(hours=23, minutes=59) < lifetime <= timedelta(hours=24, minutes=1)
    assert account.last_login_at is not None


@pytest.mark.parametrize("typed", ["ANVAR", "Anvar", "  anvar  "])
async def test_username_is_case_insensitive_and_trimmed(
    db_session: AsyncSession, typed: str
) -> None:
    await create_user(db_session)

    await login(db_session, username=typed)


async def test_wrong_password_and_unknown_user_give_identical_error(
    db_session: AsyncSession,
) -> None:
    await create_user(db_session)
    service = AuthService(db_session)

    with pytest.raises(InvalidCredentialsError) as wrong_password:
        await service.login("anvar", "9999", **CLIENT)
    with pytest.raises(InvalidCredentialsError) as unknown_user:
        await service.login("yoq_odam", PASSWORD, **CLIENT)

    # Qaysi biri xatoligi bilinmasligi kerak (7-band)
    assert wrong_password.value.message == unknown_user.value.message == "Login yoki parol xato"


async def test_deleted_account_cannot_login(db_session: AsyncSession) -> None:
    account = await create_user(db_session)
    account.deleted_at = utcnow()

    with pytest.raises(InvalidCredentialsError):
        await login(db_session)


async def test_archived_employee_cannot_login(db_session: AsyncSession) -> None:
    account = await create_user(db_session)
    employee = await db_session.get(Employee, account.employee_id)
    assert employee is not None
    employee.archived_at = utcnow()

    with pytest.raises(InvalidCredentialsError):
        await login(db_session)


async def test_locked_account_rejects_even_correct_password(db_session: AsyncSession) -> None:
    account = await create_user(db_session)
    account.locked_at = utcnow()

    with pytest.raises(AccountLockedError) as error:
        await login(db_session)
    assert error.value.status_code == 423
    assert error.value.message == "Hisob bloklandi, administratorga murojaat qiling"


async def test_superadmin_login(db_session: AsyncSession) -> None:
    db_session.add(
        UserAccount(username="xusanboy", is_superadmin=True, password_hash=hash_password(PASSWORD))
    )
    await db_session.flush()

    pair = await login(db_session, username="xusanboy")

    assert pair.role is Role.SUPERADMIN


async def test_kassir_second_login_closes_first_session(db_session: AsyncSession) -> None:
    account = await create_user(db_session, role=Role.KASSIR)

    first = await login(db_session)
    await login(db_session)

    by_id = {s.id: s for s in await sessions_of(db_session, account.id)}
    first_session = by_id[decode_access_token(first.access_token).session_id]
    assert first_session.revoked_reason == RevokeReason.NEW_LOGIN
    assert sum(s.revoked_at is None for s in by_id.values()) == 1


async def test_admin_can_be_logged_in_on_two_devices(db_session: AsyncSession) -> None:
    account = await create_user(db_session, username="dilnoza", role=Role.ADMIN)

    await login(db_session, username="dilnoza")
    await login(db_session, username="dilnoza")

    assert all(s.revoked_at is None for s in await sessions_of(db_session, account.id))


# ================================================================== refresh
async def test_refresh_rotates_token_and_keeps_absolute_expiry(db_session: AsyncSession) -> None:
    account = await create_user(db_session)
    first = await login(db_session)

    second = await AuthService(db_session).refresh(first.refresh_token, **CLIENT)

    assert second.refresh_token != first.refresh_token
    assert second.refresh_expires_at == first.refresh_expires_at  # muddat uzaymadi
    sessions = {s.id: s for s in await sessions_of(db_session, account.id)}
    old = sessions[decode_access_token(first.access_token).session_id]
    new = sessions[decode_access_token(second.access_token).session_id]
    assert old.revoked_reason == RevokeReason.ROTATED
    assert new.revoked_at is None
    assert new.family_id == old.family_id


async def test_reused_refresh_token_revokes_whole_family(db_session: AsyncSession) -> None:
    account = await create_user(db_session)
    stolen = await login(db_session)
    service = AuthService(db_session)
    await service.refresh(stolen.refresh_token, **CLIENT)  # egasi refresh qildi

    with pytest.raises(RefreshTokenReusedError):
        await service.refresh(stolen.refresh_token, **CLIENT)  # o'g'ri eski tokenni yubordi

    assert all(s.revoked_at is not None for s in await sessions_of(db_session, account.id))


async def test_unknown_refresh_token_is_rejected(db_session: AsyncSession) -> None:
    with pytest.raises(SessionInvalidError):
        await AuthService(db_session).refresh("bunday-token-yoq", **CLIENT)


async def test_expired_session_cannot_be_refreshed(db_session: AsyncSession) -> None:
    account = await create_user(db_session)
    pair = await login(db_session)
    past = utcnow() - timedelta(hours=30)
    await db_session.execute(
        update(AuthSession)
        .where(AuthSession.account_id == account.id)
        .values(created_at=past, absolute_expires_at=past + timedelta(hours=24))
    )

    with pytest.raises(SessionExpiredError):
        await AuthService(db_session).refresh(pair.refresh_token, **CLIENT)


async def test_refresh_fails_after_account_deleted(db_session: AsyncSession) -> None:
    account = await create_user(db_session)
    pair = await login(db_session)
    account.deleted_at = utcnow()

    with pytest.raises(SessionInvalidError):
        await AuthService(db_session).refresh(pair.refresh_token, **CLIENT)


# ================================================================== logout
async def test_logout_invalidates_refresh_and_access_immediately(db_session: AsyncSession) -> None:
    await create_user(db_session)
    pair = await login(db_session)
    service = AuthService(db_session)

    await service.logout(decode_access_token(pair.access_token).session_id)

    with pytest.raises(SessionInvalidError):
        await service.refresh(pair.refresh_token, **CLIENT)
    with pytest.raises(SessionInvalidError):
        await service.authenticate(pair.access_token)  # 15 daqiqa kutilmaydi


# ================================================================== authenticate
async def test_authenticate_returns_current_user(db_session: AsyncSession) -> None:
    account = await create_user(db_session, role=Role.OMBORCHI)
    pair = await login(db_session)

    user = await AuthService(db_session).authenticate(pair.access_token)

    assert user.account_id == account.id
    assert user.role is Role.OMBORCHI
    assert user.employee_id == account.employee_id


async def test_password_change_invalidates_old_access_token(db_session: AsyncSession) -> None:
    account = await create_user(db_session)
    pair = await login(db_session)
    account.token_version += 1  # admin parolni almashtirdi (A-007)

    with pytest.raises(SessionInvalidError):
        await AuthService(db_session).authenticate(pair.access_token)


async def test_role_change_is_visible_on_next_request(db_session: AsyncSession) -> None:
    account = await create_user(db_session, role=Role.KASSIR)
    pair = await login(db_session)
    employee = await db_session.get(Employee, account.employee_id)
    assert employee is not None
    employee.role = Role.OMBORCHI.value  # token_version oshirilmasa ham rol bazadan olinadi

    user = await AuthService(db_session).authenticate(pair.access_token)

    assert user.role is Role.OMBORCHI


async def test_all_auth_errors_are_app_errors() -> None:
    # Global handler ularni yagona JSON formatga o'giradi
    for error in (
        InvalidCredentialsError,
        AccountLockedError,
        SessionInvalidError,
        SessionExpiredError,
        RefreshTokenReusedError,
    ):
        assert issubclass(error, AppError)
