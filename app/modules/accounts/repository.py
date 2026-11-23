"""Akkauntlar uchun bazaga so'rovlar. Biznes-qoida yo'q — faqat SQL."""

from datetime import date

from sqlalchemy import Select, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.core.pagination import PageParams
from app.core.roles import Role
from app.core.sql import escape_like
from app.core.time import TASHKENT_TZ
from app.modules.accounts.models import UserAccount
from app.modules.accounts.schemas import AccountStatusFilter
from app.modules.employees.models import Employee


def _visible() -> Select[UserAccount]:
    """Superadmin hech qachon ko'rinmaydi (R-003); "o'chirilgan" xodimlarning loginlari ham.

    Xodim JOIN bilan bitta so'rovda yuklanadi (contains_eager) — N+1 yo'q.
    """
    return (
        select(UserAccount)
        .join(UserAccount.employee)
        .options(contains_eager(UserAccount.employee))
        .where(UserAccount.is_superadmin.is_(False), Employee.anonymized_at.is_(None))
    )


async def get(session: AsyncSession, account_id: int) -> UserAccount | None:
    stmt = _visible().where(UserAccount.id == account_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def username_taken(session: AsyncSession, username: str) -> bool:
    # O'chirilganlar ham hisoblanadi: username qayta ishlatilmaydi (A-010)
    return bool(await session.scalar(select(exists().where(UserAccount.username == username))))


async def has_active_account(session: AsyncSession, employee_id: int) -> bool:
    stmt = select(
        exists().where(UserAccount.employee_id == employee_id, UserAccount.deleted_at.is_(None))
    )
    return bool(await session.scalar(stmt))


async def search(
    session: AsyncSession,
    params: PageParams,
    *,
    status: AccountStatusFilter,
    text_query: str | None,
    role: Role | None,
    created_from: date | None,
    created_to: date | None,
) -> tuple[list[UserAccount], int]:
    stmt = _visible()
    if status is AccountStatusFilter.DELETED:
        stmt = stmt.where(UserAccount.deleted_at.is_not(None))
    else:
        stmt = stmt.where(UserAccount.deleted_at.is_(None))
        if status is AccountStatusFilter.LOCKED:
            stmt = stmt.where(UserAccount.locked_at.is_not(None))
    if text_query:
        pattern = f"%{escape_like(text_query.strip())}%"
        full_name = Employee.first_name + " " + Employee.last_name
        stmt = stmt.where(
            or_(
                UserAccount.username.ilike(pattern, escape="\\"),
                full_name.ilike(pattern, escape="\\"),
            )
        )
    if role is not None:
        stmt = stmt.where(Employee.role == role.value)
    created_day = func.date(func.timezone(TASHKENT_TZ.key, UserAccount.created_at))
    if created_from:
        stmt = stmt.where(created_day >= created_from)
    if created_to:
        stmt = stmt.where(created_day <= created_to)

    total = await session.scalar(select(func.count()).select_from(stmt.subquery()))
    page = stmt.order_by(UserAccount.created_at.desc(), UserAccount.id.desc())
    rows = await session.execute(page.offset(params.offset).limit(params.size))
    return list(rows.scalars()), int(total or 0)
