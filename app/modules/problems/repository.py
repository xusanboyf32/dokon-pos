"""Muammolar uchun bazaga so'rovlar. Biznes-qoida yo'q — faqat SQL."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import Select, func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import PageParams
from app.core.time import TASHKENT_TZ
from app.modules.problems.models import Problem, ProblemStatus, Resolution


async def open_or_bump(
    session: AsyncSession,
    *,
    type_: str,
    group_key: str,
    entity_type: str,
    entity_id: int,
    subject_employee_id: int | None,
    superadmin_only: bool,
) -> None:
    """Ochiq muammo yo'q — ochadi; bor — `occurrences` +1 va vaqtni yangilaydi (N-002).

    "INSERT ... ON CONFLICT DO UPDATE" (upsert) — bitta atomar SQL. Python'da
    "bormi? → yo'q → qo'sh" qilinsa, ikki so'rov bir vaqtda kelganda ikkalasi "yo'q"
    deb ko'rib, ikki qator ochardi. Bu yerda baza buni o'zi hal qiladi.
    """
    stmt = insert(Problem).values(
        type=type_,
        group_key=group_key,
        entity_type=entity_type,
        entity_id=entity_id,
        subject_employee_id=subject_employee_id,
        superadmin_only=superadmin_only,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[Problem.group_key],
        index_where=text("status = 'open'"),  # qisman indeks: faqat ochiqlar orasida
        set_={
            "occurrences": Problem.occurrences + 1,
            "last_occurred_at": func.now(),
        },
    )
    await session.execute(stmt)


async def resolve_open(
    session: AsyncSession,
    *,
    group_key: str,
    resolution: Resolution,
    resolved_by_account_id: int | None,
    note: str | None = None,
) -> int:
    """Shu kalitdagi ochiq muammoni yopadi. Nechta yopilgani qaytadi (0 yoki 1)."""
    stmt = (
        update(Problem)
        .where(Problem.group_key == group_key, Problem.status == ProblemStatus.OPEN.value)
        .values(
            status=ProblemStatus.RESOLVED.value,
            resolved_at=func.now(),
            resolution=resolution.value,
            resolved_by_account_id=resolved_by_account_id,
            resolution_note=note,
        )
    )
    result = await session.execute(stmt)
    return int(result.rowcount)  # type: ignore[attr-defined]


def _visible(include_superadmin_only: bool) -> Select[Problem]:
    stmt = select(Problem)
    if not include_superadmin_only:
        stmt = stmt.where(Problem.superadmin_only.is_(False))
    return stmt


async def count_open(session: AsyncSession, *, include_superadmin_only: bool) -> int:
    stmt = _visible(include_superadmin_only).where(Problem.status == ProblemStatus.OPEN.value)
    return int(await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)


def _tashkent_day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=TASHKENT_TZ)


async def search(
    session: AsyncSession,
    params: PageParams,
    *,
    statuses: list[str],
    type_: str | None,
    employee_id: int | None,
    date_from: date | None,
    date_to: date | None,
    include_superadmin_only: bool,
) -> tuple[list[Problem], int]:
    """Eng yangisi tepada (oxirgi takrorlanish vaqti bo'yicha) — N-004."""
    stmt = _visible(include_superadmin_only).where(Problem.status.in_(statuses))
    if type_:
        stmt = stmt.where(Problem.type == type_)
    if employee_id is not None:
        stmt = stmt.where(Problem.subject_employee_id == employee_id)
    if date_from:
        stmt = stmt.where(Problem.last_occurred_at >= _tashkent_day_start(date_from))
    if date_to:
        stmt = stmt.where(
            Problem.last_occurred_at < _tashkent_day_start(date_to + timedelta(days=1))
        )

    total = int(await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    stmt = (
        stmt.order_by(Problem.last_occurred_at.desc(), Problem.id.desc())
        .offset(params.offset)
        .limit(params.size)
    )
    return list((await session.execute(stmt)).scalars()), total
