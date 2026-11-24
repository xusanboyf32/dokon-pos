"""Auth amallari jurnalga to'g'ri tushishi (AU-004, AU-012)."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts.superadmin import create_superadmin, unlock_superadmin
from app.modules.audit.catalog import AuditAction
from app.modules.audit.models import AuditEvent
from app.modules.auth.exceptions import RefreshTokenReusedError
from app.modules.auth.service import AuthService
from tests.integration.test_auth_service import CLIENT, create_user, login
from tests.integration.test_lockout import fail_times, lock


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


async def test_lock_is_recorded_once_by_system(
    db_session: AsyncSession, service: AuthService
) -> None:
    """AU-004: 9 ta xato — jurnalda yo'q; 10-chisida blok — bitta yozuv, "Tizim" nomidan."""
    account = await create_user(db_session)

    await lock(service)

    [event] = await events(db_session, AuditAction.AUTH_LOCKED_PERMANENT)
    assert event.actor_account_id is None
    assert event.entity_id == account.id
    assert event.severity == "critical"


async def test_unknown_username_leaves_no_trace(
    db_session: AsyncSession, service: AuthService
) -> None:
    await fail_times(service, 15, username="yoq_odam")

    assert await db_session.scalar(select(AuditEvent.id).limit(1)) is None


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


async def test_superadmin_cli_actions_are_hidden_from_admin(db_session: AsyncSession) -> None:
    account = await create_superadmin(db_session, "boss", "parol123", "parol123")
    await unlock_superadmin(db_session)

    created = await events(db_session, AuditAction.ACCOUNT_SUPERADMIN_CREATED)
    unlocked = await events(db_session, AuditAction.ACCOUNT_SUPERADMIN_UNLOCKED)
    for event in (*created, *unlocked):
        assert event.entity_id == account.id
        assert event.superadmin_only is True
    assert len(created) == len(unlocked) == 1
