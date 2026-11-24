"""Audit jurnali uchun bazaga so'rovlar. Biznes-qoida yo'q — faqat SQL."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import CursorParams
from app.core.time import TASHKENT_TZ
from app.modules.accounts.models import UserAccount
from app.modules.audit.catalog import Severity
from app.modules.audit.models import AuditEvent
from app.modules.audit.schemas import AuditFilters
from app.modules.employees.models import Employee

_SEVERITY_AT_LEAST: dict[Severity, list[str]] = {
    Severity.INFO: [s.value for s in Severity],
    Severity.IMPORTANT: [Severity.IMPORTANT.value, Severity.CRITICAL.value],
    Severity.CRITICAL: [Severity.CRITICAL.value],
}


async def add(session: AsyncSession, event: AuditEvent) -> AuditEvent:
    """Yozuvni chaqiruvchining tranzaksiyasiga qo'shadi. Commit — chaqiruvchida (AU-009)."""
    session.add(event)
    await session.flush()
    return event


def _tashkent_day_start(day: date) -> datetime:
    """Toshkent sanasining boshlanishi (00:00) — UTC'dagi aniq vaqt sifatida."""
    return datetime.combine(day, time.min, tzinfo=TASHKENT_TZ)


async def search(
    session: AsyncSession,
    filters: AuditFilters,
    page: CursorParams,
    *,
    include_superadmin_only: bool,
) -> list[AuditEvent]:
    """Eng yangisi tepada. `limit + 1` ta o'qiladi — "yana bormi?" ni bilish uchun."""
    stmt = select(AuditEvent)

    if not include_superadmin_only:
        stmt = stmt.where(AuditEvent.superadmin_only.is_(False))  # AU-001
    stmt = stmt.where(AuditEvent.severity.in_(_SEVERITY_AT_LEAST[filters.min_severity]))

    # Sana chegaralari Python'da UTC vaqtga aylantiriladi, ustunning o'zi o'zgartirilmaydi —
    # shunda baza `occurred_at` indeksidan foydalana oladi.
    if filters.date_from:
        stmt = stmt.where(AuditEvent.occurred_at >= _tashkent_day_start(filters.date_from))
    if filters.date_to:
        next_day = _tashkent_day_start(filters.date_to + timedelta(days=1))
        stmt = stmt.where(AuditEvent.occurred_at < next_day)

    if filters.actor_employee_id is not None:
        actor_accounts = select(UserAccount.id).where(
            UserAccount.employee_id == filters.actor_employee_id
        )
        stmt = stmt.where(AuditEvent.actor_account_id.in_(actor_accounts))
    if filters.module:
        stmt = stmt.where(AuditEvent.action.startswith(f"{filters.module.value}."))
    if filters.actions:
        stmt = stmt.where(AuditEvent.action.in_([a.value for a in filters.actions]))
    if filters.entity_type:
        stmt = stmt.where(AuditEvent.entity_type == filters.entity_type)
    if filters.entity_id is not None:
        stmt = stmt.where(AuditEvent.entity_id == filters.entity_id)

    if page.after is not None:
        # "(vaqt, id) oxirgi ko'rilgandan kichik" — keyingi sahifa shu yerdan boshlanadi
        stmt = stmt.where(tuple_(AuditEvent.occurred_at, AuditEvent.id) < page.after)

    stmt = stmt.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(page.limit + 1)
    return list((await session.execute(stmt)).scalars())


# ------------------------------------------------------------------ ismlar (N+1 siz)
@dataclass(frozen=True, slots=True)
class AccountName:
    username: str
    is_superadmin: bool
    owner_name: str | None  # xodimning ismi (superadmin'da yo'q)


def _full_name(employee: Employee) -> str:
    return f"{employee.first_name} {employee.last_name}"


async def account_names(session: AsyncSession, ids: set[int]) -> dict[int, AccountName]:
    """Bitta so'rov bilan hamma akkauntlar va ularning egalari (50 ta yozuv → 1 so'rov)."""
    if not ids:
        return {}
    stmt = (
        select(UserAccount, Employee)
        .outerjoin(Employee, Employee.id == UserAccount.employee_id)
        .where(UserAccount.id.in_(ids))
    )
    return {
        account.id: AccountName(
            username=account.username,
            is_superadmin=account.is_superadmin,
            owner_name=_full_name(employee) if employee else None,
        )
        for account, employee in (await session.execute(stmt)).all()
    }


async def employee_names(session: AsyncSession, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    stmt = select(Employee).where(Employee.id.in_(ids))
    return {e.id: _full_name(e) for e in (await session.execute(stmt)).scalars()}
