"""`employees` jadvalidagi qoidalarni BAZANING O'ZI kafolatlashini tekshiradi.

Python kodida xato bo'lsa ham, baza noto'g'ri ma'lumotni qabul qilmasligi kerak.
"""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.employees.models import Employee


def make_employee(**overrides: Any) -> Employee:
    data: dict[str, Any] = {
        "first_name": "Anvar",
        "last_name": "Karimov",
        "birth_date": date(2001, 5, 12),
        "gender": "male",
        "phone": "+998901234567",
        "role": "kassir",
        "salary": Decimal("4000000.00"),
        "photo_path": "employees/anvar.jpg",
    }
    data.update(overrides)
    return Employee(**data)


async def test_valid_employee_is_saved_with_utc_timestamps(db_session: AsyncSession) -> None:
    employee = make_employee()
    db_session.add(employee)
    await db_session.flush()
    await db_session.refresh(employee)

    assert employee.id is not None
    assert employee.created_at.tzinfo is not None  # timestamptz
    assert employee.salary == Decimal("4000000.00")  # Decimal, float emas
    assert employee.archived_at is None


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"phone": "901234567"}, "ck_employees_phone_format"),
        ({"phone": "+99890123456"}, "ck_employees_phone_format"),  # 1 raqam kam
        ({"salary": Decimal("-1")}, "ck_employees_salary_not_negative"),
        ({"role": "taminotchi"}, "ck_employees_role_valid"),  # ta'minotchi xodim emas
        ({"role": "direktor"}, "ck_employees_role_valid"),
        ({"gender": "other"}, "ck_employees_gender_valid"),
        ({"birth_date": date(1899, 12, 31)}, "ck_employees_birth_date_sane"),
    ],
)
async def test_database_rejects_invalid_values(
    db_session: AsyncSession, overrides: dict[str, Any], constraint: str
) -> None:
    db_session.add(make_employee(**overrides))

    with pytest.raises(IntegrityError, match=constraint):
        await db_session.flush()


async def test_phone_must_be_unique(db_session: AsyncSession) -> None:
    db_session.add(make_employee(phone="+998901112233"))
    await db_session.flush()

    # Bir xil ism-familiya — ruxsat, lekin telefon bir xil bo'lishi mumkin emas (E-003)
    db_session.add(make_employee(phone="+998901112233"))
    with pytest.raises(IntegrityError, match="uq_employees_phone"):
        await db_session.flush()


async def test_same_name_with_different_phone_is_allowed(db_session: AsyncSession) -> None:
    db_session.add_all([make_employee(phone="+998900000001"), make_employee(phone="+998900000002")])

    await db_session.flush()  # xato bo'lmasligi kerak


async def test_ids_are_sequential(db_session: AsyncSession) -> None:
    employees = [make_employee(phone=f"+99890000001{i}") for i in range(3)]
    db_session.add_all(employees)
    await db_session.flush()

    ids = [e.id for e in employees]
    assert ids == list(range(ids[0], ids[0] + 3))
