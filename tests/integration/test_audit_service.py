"""`audit.record()` — yozuv qanday to'ldirilishi (AU-001, AU-005, AU-006, AU-009)."""

from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_context import RequestContext, reset_request_context, set_request_context
from app.core.roles import Role
from app.modules.audit import service as audit
from app.modules.audit.catalog import AuditAction
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import ReasonRequiredError
from tests.integration.test_auth_sessions_table import create_account


@dataclass(frozen=True)
class FakeActor:
    account_id: int
    role: Role


@pytest.fixture
def request_context() -> Iterator[RequestContext]:
    context = RequestContext(request_id="req-1", ip="10.0.0.5", user_agent="Mozilla/5.0")
    token = set_request_context(context)
    yield context
    reset_request_context(token)


async def count_events(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(AuditEvent)) or 0)


async def test_record_fills_all_fields(
    db_session: AsyncSession, request_context: RequestContext
) -> None:
    account = await create_account(db_session)

    event = await audit.record(
        db_session,
        actor=FakeActor(account.id, Role.ADMIN),
        action=AuditAction.EMPLOYEE_SALARY_CHANGED,
        entity=("employee", 12),
        changes={"salary": (Decimal("3000000.00"), Decimal("3500000.00"))},
    )

    assert event.id > 0
    assert event.actor_account_id == account.id
    assert event.actor_role == "admin"
    assert event.action == "employee.salary_changed"
    assert event.severity == "important"  # katalogdan
    assert (event.entity_type, event.entity_id) == ("employee", 12)
    assert event.changes == {"salary": ["3000000.00", "3500000.00"]}
    assert event.superadmin_only is False
    assert (event.request_id, event.ip, event.user_agent) == ("req-1", "10.0.0.5", "Mozilla/5.0")


async def test_system_action_has_no_actor(db_session: AsyncSession) -> None:
    event = await audit.record(
        db_session, actor=None, action=AuditAction.AUTH_LOCKED_TEMPORARY, entity=("account", 1)
    )

    assert event.actor_account_id is None
    assert event.actor_role is None
    assert event.request_id is None  # so'rovdan tashqarida (CLI) kontekst bo'sh


async def test_superadmin_actions_are_hidden_from_admin(db_session: AsyncSession) -> None:
    account = await create_account(db_session)

    event = await audit.record(
        db_session,
        actor=FakeActor(account.id, Role.SUPERADMIN),
        action=AuditAction.EMPLOYEE_ARCHIVED,
        entity=("employee", 1),
    )

    assert event.superadmin_only is True


async def test_actions_about_superadmin_are_hidden_from_admin(db_session: AsyncSession) -> None:
    event = await audit.record(
        db_session,
        actor=None,
        action=AuditAction.AUTH_LOCKED_PERMANENT,
        entity=("account", 1),
        concerns_superadmin=True,
    )

    assert event.superadmin_only is True
    assert event.severity == "critical"


@pytest.mark.parametrize("reason", [None, "", "   "])
async def test_reason_is_required_for_sensitive_actions(
    db_session: AsyncSession, reason: str | None
) -> None:
    with pytest.raises(ReasonRequiredError):
        await audit.record(
            db_session,
            actor=None,
            action=AuditAction.ACCOUNT_UNLOCKED,
            entity=("account", 1),
            reason=reason,
        )

    assert await count_events(db_session) == 0


async def test_reason_is_trimmed(db_session: AsyncSession) -> None:
    event = await audit.record(
        db_session,
        actor=None,
        action=AuditAction.ACCOUNT_UNLOCKED,
        entity=("account", 1),
        reason="  Parolni unutgan  ",
    )

    assert event.reason == "Parolni unutgan"


async def test_too_long_reason_is_rejected(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="500"):
        await audit.record(
            db_session,
            actor=None,
            action=AuditAction.ACCOUNT_UNLOCKED,
            entity=("account", 1),
            reason="x" * 501,
        )


async def test_event_is_rolled_back_together_with_the_action(db_session: AsyncSession) -> None:
    """AU-009: amal bekor bo'lsa — audit yozuvi ham qolmaydi."""
    savepoint = await db_session.begin_nested()
    await audit.record(
        db_session, actor=None, action=AuditAction.EMPLOYEE_CREATED, entity=("employee", 1)
    )
    await savepoint.rollback()

    assert await count_events(db_session) == 0


async def test_no_changes_is_stored_as_sql_null(db_session: AsyncSession) -> None:
    """JSON 'null' emas, haqiqiy NULL — aks holda `changes IS NULL` filtri ishlamaydi."""
    await audit.record(
        db_session, actor=None, action=AuditAction.EMPLOYEE_CREATED, entity=("employee", 1)
    )

    stmt = select(func.count()).select_from(AuditEvent).where(AuditEvent.changes.is_(None))
    assert await db_session.scalar(stmt) == 1
