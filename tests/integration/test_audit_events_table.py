"""`audit_events` qoidalarini bazaning o'zi kafolatlashini tekshiradi (AU-010)."""

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditEvent
from tests.integration.test_auth_sessions_table import create_account


def make_event(**overrides: Any) -> AuditEvent:
    data: dict[str, Any] = {
        "action": "employee.salary_changed",
        "severity": "important",
        "entity_type": "employee",
        "entity_id": 1,
        "superadmin_only": False,
    }
    data.update(overrides)
    return AuditEvent(**data)


async def insert_event(session: AsyncSession) -> AuditEvent:
    event = make_event()
    session.add(event)
    await session.flush()
    return event


async def test_event_is_saved_with_server_time(db_session: AsyncSession) -> None:
    account = await create_account(db_session)
    event = make_event(
        actor_account_id=account.id, actor_role="admin", changes={"salary": ["1.00", "2.00"]}
    )
    db_session.add(event)
    await db_session.flush()
    await db_session.refresh(event)

    assert event.id > 0
    assert event.occurred_at.tzinfo is not None


async def test_update_is_forbidden(db_session: AsyncSession) -> None:
    event = await insert_event(db_session)

    with pytest.raises(DBAPIError, match="faqat qo'shiladi"):
        await db_session.execute(
            text("UPDATE audit_events SET reason = 'x' WHERE id = :id"), {"id": event.id}
        )


async def test_delete_is_forbidden(db_session: AsyncSession) -> None:
    event = await insert_event(db_session)

    with pytest.raises(DBAPIError, match="faqat qo'shiladi"):
        await db_session.execute(text("DELETE FROM audit_events WHERE id = :id"), {"id": event.id})


async def test_truncate_is_forbidden(db_session: AsyncSession) -> None:
    await insert_event(db_session)

    with pytest.raises(DBAPIError, match="faqat qo'shiladi"):
        await db_session.execute(text("TRUNCATE audit_events"))


@pytest.mark.parametrize(
    "overrides",
    [
        {"action": "Employee.Updated"},  # katta harf
        {"action": "employee"},  # modul.amal emas
        {"severity": "low"},
        {"actor_role": "admin"},  # rol bor, aktyor yo'q
        {"actor_role": "direktor"},
        {"entity_type": "Employee"},
        {"reason": "   "},
        {"changes": ["salary"]},  # obyekt emas, ro'yxat
    ],
)
async def test_invalid_rows_are_rejected(
    db_session: AsyncSession, overrides: dict[str, Any]
) -> None:
    db_session.add(make_event(**overrides))

    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_actor_without_role_is_rejected(db_session: AsyncSession) -> None:
    account = await create_account(db_session)
    db_session.add(make_event(actor_account_id=account.id))

    with pytest.raises(IntegrityError):
        await db_session.flush()
