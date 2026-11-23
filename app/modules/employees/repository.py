"""Xodimlar uchun bazaga so'rovlar. Biznes-qoida yo'q — faqat SQL."""

from datetime import date

from sqlalchemy import Select, delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.core.roles import Role
from app.core.sql import escape_like
from app.core.time import TASHKENT_TZ
from app.modules.accounts.models import UserAccount
from app.modules.employees.models import Employee, EmployeePosition
from app.modules.employees.schemas import EmployeeStatus


def _visible() -> Select[Employee]:
    # "O'chirilgan" (anonimlashtirilgan) xodim hech qaysi ro'yxatda ko'rinmaydi
    return select(Employee).where(Employee.anonymized_at.is_(None))


async def get(session: AsyncSession, employee_id: int) -> Employee | None:
    stmt = _visible().where(Employee.id == employee_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def phone_taken(session: AsyncSession, phone: str, exclude_id: int | None = None) -> bool:
    stmt = select(exists().where(Employee.phone == phone, Employee.id != (exclude_id or 0)))
    return bool(await session.scalar(stmt))


async def search(
    session: AsyncSession,
    params: PageParams,
    *,
    status: EmployeeStatus,
    text_query: str | None,
    roles: frozenset[Role] | None,
    created_from: date | None,
    created_to: date | None,
) -> tuple[list[Employee], int]:
    stmt = _visible()
    if status is EmployeeStatus.ACTIVE:
        stmt = stmt.where(Employee.archived_at.is_(None))
    else:
        stmt = stmt.where(Employee.archived_at.is_not(None))
    if text_query:
        pattern = f"%{escape_like(text_query.strip())}%"
        full_name = Employee.first_name + " " + Employee.last_name
        stmt = stmt.where(
            or_(
                Employee.first_name.ilike(pattern, escape="\\"),
                Employee.last_name.ilike(pattern, escape="\\"),
                full_name.ilike(pattern, escape="\\"),
            )
        )
    if roles is not None:
        stmt = stmt.where(Employee.role.in_([r.value for r in roles]))
    # Sana do'kon vaqtida (Toshkent) hisoblanadi, UTC'da emas: 01:00 da qo'shilgan
    # xodim UTC bo'yicha "kecha" bo'lib qolmasin
    created_day = func.date(func.timezone(TASHKENT_TZ.key, Employee.created_at))
    if created_from:
        stmt = stmt.where(created_day >= created_from)
    if created_to:
        stmt = stmt.where(created_day <= created_to)

    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    page = stmt.order_by(Employee.created_at.desc(), Employee.id.desc())
    rows = await session.execute(page.offset(params.offset).limit(params.size))
    return list(rows.scalars()), int(total or 0)


async def count_by_role(session: AsyncSession) -> dict[str, int]:
    stmt = (
        _visible()
        .with_only_columns(Employee.role, func.count())
        .where(Employee.archived_at.is_(None))
        .group_by(Employee.role)
    )
    return {role: count for role, count in (await session.execute(stmt)).all()}


async def open_position(session: AsyncSession, employee_id: int) -> EmployeePosition | None:
    stmt = select(EmployeePosition).where(
        EmployeePosition.employee_id == employee_id, EmployeePosition.valid_to.is_(None)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def positions(session: AsyncSession, employee_id: int) -> list[EmployeePosition]:
    stmt = (
        select(EmployeePosition)
        .where(EmployeePosition.employee_id == employee_id)
        .order_by(EmployeePosition.valid_from.desc())
    )
    return list((await session.execute(stmt)).scalars())


async def accounts_of(session: AsyncSession, employee_id: int) -> list[UserAccount]:
    stmt = select(UserAccount).where(UserAccount.employee_id == employee_id)
    return list((await session.execute(stmt)).scalars())


async def delete_completely(session: AsyncSession, employee: Employee) -> None:
    await session.execute(
        delete(EmployeePosition).where(EmployeePosition.employee_id == employee.id)
    )
    await session.delete(employee)
