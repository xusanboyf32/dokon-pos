"""Auth amallari jurnalga to'g'ri tushishi (AU-004, AU-012)."""

import pytest
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts.superadmin import create_superadmin, unlock_superadmin
from app.modules.audit.catalog import AuditAction
from app.modules.audit.models import AuditEvent
from app.modules.auth.exceptions import (
    AccountLockedError,
    AccountTemporarilyLockedError,
    RefreshTokenReusedError,
)
from app.modules.auth.lockout import LoginGuard
from app.modules.auth.service import AuthService
from tests.integration.test_auth_service import CLIENT, create_user, login
from tests.integration.test_lockout import end_temporary_block, fail_times, wrong_login


async def events(session: AsyncSession, action: AuditAction) -> list[AuditEvent]:
    stmt = select(AuditEvent).where(AuditEvent.action == action.value).order_by(AuditEvent.id)
    return list((await session.execute(stmt)).scalars())


async def test_successful_login_is_recorded_with_actor(
    db_session: AsyncSession, service: AuthService
) -> None:
    account = await create_user(db_session)

    await login(service)

    [event] = await events(db_session, AuditAction.AUTH_LOGIN_SUCCESS)
    assert (event.actor_account_id, event.actor_role) == (account.id, "kassir")
    assert (event.entity_type, event.entity_id) == ("account", account.id)
    assert event.superadmin_only is False


async def test_wrong_password_alone_is_not_recorded(
    db_session: AsyncSession, service: AuthService
) -> None:
    """AU-004: har bir xato urinish — faqat logga, jurnalga emas."""
    await create_user(db_session)

    await fail_times(service, 2)

    assert await db_session.scalar(select(AuditEvent.id).limit(1)) is None


async def test_temporary_and_permanent_locks_are_recorded_by_system(
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

    [temporary] = await events(db_session, AuditAction.AUTH_LOCKED_TEMPORARY)
    [permanent] = await events(db_session, AuditAction.AUTH_LOCKED_PERMANENT)
    for event in (temporary, permanent):
        assert event.actor_account_id is None  # "Tizim"
        assert event.entity_id == account.id
    assert permanent.severity == "critical"


async def test_lock_of_unknown_username_is_not_recorded(
    db_session: AsyncSession, service: AuthService
) -> None:
    await fail_times(service, 4, username="yoq_odam")
    with pytest.raises(AccountTemporarilyLockedError):
        await wrong_login(service, username="yoq_odam")

    assert await events(db_session, AuditAction.AUTH_LOCKED_TEMPORARY) == []


async def test_refresh_token_reuse_is_recorded_as_critical(
    db_session: AsyncSession, service: AuthService
) -> None:
    account = await create_user(db_session)
    stolen = await login(service)
    await service.refresh(stolen.refresh_token, **CLIENT)

    with pytest.raises(RefreshTokenReusedError):
        await service.refresh(stolen.refresh_token, **CLIENT)

    [event] = await events(db_session, AuditAction.AUTH_TOKEN_REUSE_DETECTED)
    assert (event.entity_id, event.severity, event.actor_account_id) == (
        account.id,
        "critical",
        None,
    )


async def test_superadmin_cli_actions_are_hidden_from_admin(
    db_session: AsyncSession, guard: LoginGuard
) -> None:
    account = await create_superadmin(db_session, "boss", "parol123", "parol123")
    await unlock_superadmin(db_session, guard)

    created = await events(db_session, AuditAction.ACCOUNT_SUPERADMIN_CREATED)
    unlocked = await events(db_session, AuditAction.ACCOUNT_SUPERADMIN_UNLOCKED)
    for event in (*created, *unlocked):
        assert event.entity_id == account.id
        assert event.superadmin_only is True
    assert len(created) == len(unlocked) == 1
