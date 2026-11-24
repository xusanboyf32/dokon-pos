"""Audit jurnali uchun bazaga so'rovlar. Biznes-qoida yo'q — faqat SQL."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import Select, and_, exists, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import CursorParams
from app.core.time import TASHKENT_TZ
from app.modules.accounts.models import UserAccount
from app.modules.audit.catalog import AuditAction, Severity
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
    """Umumiy jurnal: filtrlar birga (VA) qo'llanadi (AU-018)."""
    stmt = _visible(include_superadmin_only)
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

    return await _fetch_page(session, stmt, page)


async def employee_history(
    session: AsyncSession,
    employee_id: int,
    page: CursorParams,
    *,
    include_logins: bool,
    include_superadmin_only: bool,
) -> list[AuditEvent]:
    """Xodimning o'ziga VA uning login(lar)iga oid yozuvlar — bitta ro'yxatda (AU-019)."""
    accounts_of_employee = select(UserAccount.id).where(UserAccount.employee_id == employee_id)
    stmt = _visible(include_superadmin_only).where(
        or_(
            and_(AuditEvent.entity_type == "employee", AuditEvent.entity_id == employee_id),
            and_(
                AuditEvent.entity_type == "account",
                AuditEvent.entity_id.in_(accounts_of_employee),
            ),
        )
    )
    if not include_logins:
        stmt = stmt.where(AuditEvent.action != AuditAction.AUTH_LOGIN_SUCCESS.value)
    return await _fetch_page(session, stmt, page)


async def employee_exists(session: AsyncSession, employee_id: int) -> bool:
    """O'chirilgan (anonimlashtirilgan) xodim hech qayerda ko'rinmaydi (E-009)."""
    stmt = select(exists().where(Employee.id == employee_id, Employee.anonymized_at.is_(None)))
    return bool(await session.scalar(stmt))


def _visible(include_superadmin_only: bool) -> Select[AuditEvent]:
    stmt = select(AuditEvent)
    if not include_superadmin_only:
        stmt = stmt.where(AuditEvent.superadmin_only.is_(False))  # AU-001
    return stmt


async def _fetch_page(
    session: AsyncSession, stmt: Select[AuditEvent], page: CursorParams
) -> list[AuditEvent]:
    """Eng yangisi tepada. `limit + 1` ta o'qiladi — "yana bormi?" ni bilish uchun."""
    if page.after is not None:
        # "(vaqt, id) oxirgi ko'rilgandan kichik" — keyingi sahifa shu yerdan boshlanadi
        stmt = stmt.where(tuple_(AuditEvent.occurred_at, AuditEvent.id) < page.after)
    stmt = stmt.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc()).limit(page.limit + 1)
    return list((await session.execute(stmt)).scalars())
