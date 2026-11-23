"""`user_accounts` jadvalidagi qoidalarni BAZANING O'ZI kafolatlashini tekshiradi."""

from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.modules.accounts.models import UserAccount
from app.modules.employees.models import Employee
from tests.integration.test_employees_table import make_employee

FAKE_HASH = "$argon2id$v=19$m=65536,t=3,p=4$fake"


async def create_employee(session: AsyncSession, phone: str = "+998901234567") -> Employee:
    employee = make_employee(phone=phone)
    session.add(employee)
    await session.flush()
    return employee


def make_account(**overrides: Any) -> UserAccount:
    data: dict[str, Any] = {"username": "anvar", "password_hash": FAKE_HASH}
    data.update(overrides)
    return UserAccount(**data)


async def test_employee_account_is_saved(db_session: AsyncSession) -> None:
    employee = await create_employee(db_session)
    account = make_account(employee_id=employee.id)
    db_session.add(account)
    await db_session.flush()
    await db_session.refresh(account)

    assert account.token_version == 0
    assert account.is_superadmin is False
    assert account.is_active


async def test_superadmin_account_has_no_owner_table(db_session: AsyncSession) -> None:
    db_session.add(make_account(username="xusanboy", is_superadmin=True))

    await db_session.flush()  # xato bo'lmasligi kerak


async def test_only_one_superadmin_allowed(db_session: AsyncSession) -> None:
    db_session.add(make_account(username="birinchi", is_superadmin=True))
    await db_session.flush()

    db_session.add(make_account(username="ikkinchi", is_superadmin=True))
    with pytest.raises(IntegrityError, match="uq_user_accounts_single_superadmin"):
        await db_session.flush()


async def test_account_without_owner_is_rejected(db_session: AsyncSession) -> None:
    db_session.add(make_account())

    with pytest.raises(IntegrityError, match="ck_user_accounts_exactly_one_owner"):
        await db_session.flush()


async def test_account_cannot_be_both_employee_and_superadmin(db_session: AsyncSession) -> None:
    employee = await create_employee(db_session)
    db_session.add(make_account(employee_id=employee.id, is_superadmin=True))

    with pytest.raises(IntegrityError, match="ck_user_accounts_exactly_one_owner"):
        await db_session.flush()


@pytest.mark.parametrize(
    "username",
    [
        "Anvar",  # katta harf — kichik harfda saqlanishi shart
        "an",  # 3 belgidan kam
        "a" * 51,  # 50 belgidan ko'p
        "anvar karimov",  # bo'sh joy
        "анвар",  # kirill
        "anvar@",  # ruxsat etilmagan belgi
    ],
)
async def test_invalid_username_is_rejected(db_session: AsyncSession, username: str) -> None:
    employee = await create_employee(db_session)
    db_session.add(make_account(employee_id=employee.id, username=username))

    # Uzunlik oshsa — IntegrityError emas, "value too long" (DBAPIError) keladi
    with pytest.raises(DBAPIError, match="username_format|value too long"):
        await db_session.flush()


@pytest.mark.parametrize("username", ["anvar", "anvar_1", "a.karimov", "kassir.2026"])
async def test_valid_usernames(db_session: AsyncSession, username: str) -> None:
    employee = await create_employee(db_session)
    db_session.add(make_account(employee_id=employee.id, username=username))

    await db_session.flush()


async def test_one_active_login_per_employee(db_session: AsyncSession) -> None:
    employee = await create_employee(db_session)
    db_session.add(make_account(employee_id=employee.id, username="anvar"))
    await db_session.flush()

    db_session.add(make_account(employee_id=employee.id, username="anvar2"))
    with pytest.raises(IntegrityError, match="uq_user_accounts_employee_active"):
        await db_session.flush()


async def test_new_login_allowed_after_old_one_deleted(db_session: AsyncSession) -> None:
    employee = await create_employee(db_session)
    old = make_account(employee_id=employee.id, username="anvar")
    db_session.add(old)
    await db_session.flush()

    old.deleted_at = utcnow()  # "parol o'chirildi"
    db_session.add(make_account(employee_id=employee.id, username="anvar2"))

    await db_session.flush()  # yangi login berish mumkin


async def test_deleted_username_cannot_be_reused(db_session: AsyncSession) -> None:
    first = await create_employee(db_session, phone="+998900000001")
    second = await create_employee(db_session, phone="+998900000002")
    db_session.add(make_account(employee_id=first.id, username="anvar", deleted_at=utcnow()))
    await db_session.flush()

    db_session.add(make_account(employee_id=second.id, username="anvar"))
    with pytest.raises(IntegrityError, match="uq_user_accounts_username"):
        await db_session.flush()


async def test_employee_with_account_cannot_be_hard_deleted(db_session: AsyncSession) -> None:
    employee = await create_employee(db_session)
    db_session.add(make_account(employee_id=employee.id))
    await db_session.flush()

    await db_session.delete(employee)
    with pytest.raises(IntegrityError, match="fk_user_accounts_employee_id_employees"):
        await db_session.flush()
