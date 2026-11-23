"""Lavozim tarixi va anonimlashtirish qoidalarini BAZANING O'ZI kafolatlaydi."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.modules.employees.models import EmployeePosition
from tests.integration.test_employees_table import make_employee


async def _employee_id(session: AsyncSession) -> int:
    employee = make_employee()
    session.add(employee)
    await session.flush()
    return employee.id


def _position(employee_id: int, **overrides: Any) -> EmployeePosition:
    data: dict[str, Any] = {
        "employee_id": employee_id,
        "role": "kassir",
        "salary": Decimal("4000000"),
        "valid_from": date(2026, 1, 1),
    }
    data.update(overrides)
    return EmployeePosition(**data)


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"salary": Decimal("-1")}, "ck_employee_positions_salary_not_negative"),
        ({"role": "taminotchi"}, "ck_employee_positions_role_valid"),
        ({"valid_to": date(2025, 12, 31)}, "ck_employee_positions_period_valid"),
    ],
)
async def test_position_checks(
    db_session: AsyncSession, overrides: dict[str, Any], constraint: str
) -> None:
    employee_id = await _employee_id(db_session)
    db_session.add(_position(employee_id, **overrides))

    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()


async def test_only_one_open_position_per_employee(db_session: AsyncSession) -> None:
    employee_id = await _employee_id(db_session)
    db_session.add(_position(employee_id, valid_to=date(2026, 1, 31)))
    db_session.add(_position(employee_id, valid_from=date(2026, 2, 1)))
    await db_session.flush()  # bitta yopiq + bitta ochiq — joiz

    db_session.add(_position(employee_id, valid_from=date(2026, 3, 1)))
    with pytest.raises(IntegrityError, match="uq_employee_positions_one_open"):
        await db_session.flush()


@pytest.mark.parametrize("field", ["phone", "photo_path"])
async def test_contacts_required_unless_anonymized(db_session: AsyncSession, field: str) -> None:
    db_session.add(make_employee(**{field: None}))

    with pytest.raises(IntegrityError, match="ck_employees_contacts_required"):
        await db_session.flush()


async def test_anonymized_employee_may_have_no_contacts(db_session: AsyncSession) -> None:
    db_session.add(make_employee(phone=None, photo_path=None, anonymized_at=utcnow()))

    await db_session.flush()
