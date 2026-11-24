"""🔔 Muammolar: admin bajarishi kerak bo'lgan ishlar ro'yxati (N-001…N-009).

Boshqa modullar faqat ikkita funksiyani chaqiradi — o'z tranzaksiyasi ichida (commit ularda):

    await problems.report_account_locked(session, account)      # blok qo'yilganda
    await problems.resolve_account_locked(session, account_id, actor)  # blok ochilganda
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PageParams
from app.core.roles import Role
from app.modules.accounts import names
from app.modules.accounts.models import UserAccount
from app.modules.audit.service import Actor
from app.modules.problems import repository
from app.modules.problems.models import (
    PROBLEM_LABELS,
    Problem,
    ProblemStatus,
    ProblemType,
    Resolution,
)
from app.modules.problems.schemas import PersonOut, ProblemOut, ProblemStatusFilter, QuickAction


def _group_key(type_: ProblemType, entity_type: str, entity_id: int) -> str:
    return f"{type_.value}:{entity_type}:{entity_id}"


# ================================================================== 🔒 akkaunt bloklandi
async def report_account_locked(session: AsyncSession, account: UserAccount) -> None:
    """Blok qo'yildi → muammo ochiladi (yoki takrorlanish soni oshadi)."""
    await repository.open_or_bump(
        session,
        type_=ProblemType.ACCOUNT_LOCKED.value,
        group_key=_group_key(ProblemType.ACCOUNT_LOCKED, "account", account.id),
        entity_type="account",
        entity_id=account.id,
        subject_employee_id=account.employee_id,
        superadmin_only=account.is_superadmin,
    )


async def resolve_account_locked(
    session: AsyncSession, account_id: int, actor: Actor | None
) -> None:
    """Blok ochildi → muammo o'zi yopiladi, kim ochgani yoziladi (N-003). `None` — Tizim."""
    await repository.resolve_open(
        session,
        group_key=_group_key(ProblemType.ACCOUNT_LOCKED, "account", account_id),
        resolution=Resolution.AUTO,
        resolved_by_account_id=actor.account_id if actor else None,
    )


# ================================================================== o'qish
_STATUSES: dict[ProblemStatusFilter, list[str]] = {
    ProblemStatusFilter.OPEN: [ProblemStatus.OPEN.value],
    ProblemStatusFilter.RESOLVED: [ProblemStatus.RESOLVED.value],
    ProblemStatusFilter.ALL: [s.value for s in ProblemStatus],
}


class ProblemService:
    """Admin uchun: 🔔 soni va ro'yxat. Admin superadminga oid muammolarni ko'rmaydi."""

    def __init__(self, session: AsyncSession, viewer: Actor) -> None:
        self._session = session
        self._sees_superadmin = viewer.role == Role.SUPERADMIN

    async def count_open(self) -> int:
        return await repository.count_open(
            self._session, include_superadmin_only=self._sees_superadmin
        )

    async def search(
        self,
        params: PageParams,
        *,
        status: ProblemStatusFilter = ProblemStatusFilter.OPEN,
        type_: ProblemType | None = None,
        employee_id: int | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> Page[ProblemOut]:
        rows, total = await repository.search(
            self._session,
            params,
            statuses=_STATUSES[status],
            type_=type_.value if type_ else None,
            employee_id=employee_id,
            date_from=date_from,
            date_to=date_to,
            include_superadmin_only=self._sees_superadmin,
        )
        return Page[ProblemOut].build(await self._to_out(rows), total, params)

    async def _to_out(self, rows: list[Problem]) -> list[ProblemOut]:
        # Ismlar bitta so'rov bilan (N+1 yo'q)
        account_ids = {r.entity_id for r in rows if r.entity_type == "account"}
        account_ids |= {r.resolved_by_account_id for r in rows if r.resolved_by_account_id}
        accounts = await names.account_names(self._session, account_ids)

        def label(account_id: int) -> str:
            info = accounts.get(account_id)
            return info.login_label if info else f"akkaunt #{account_id}"

        def person(account_id: int) -> str:
            info = accounts.get(account_id)
            return info.person if info else f"akkaunt #{account_id}"

        result = []
        for row in rows:
            type_ = ProblemType(row.type)
            is_open = row.status == ProblemStatus.OPEN.value
            result.append(
                ProblemOut(
                    id=row.id,
                    type=type_,
                    type_label=PROBLEM_LABELS[type_],
                    status=ProblemStatus(row.status),
                    title=f"{label(row.entity_id)} bloklandi",
                    occurrences=row.occurrences,
                    first_occurred_at=row.first_occurred_at,
                    last_occurred_at=row.last_occurred_at,
                    entity_type=row.entity_type,
                    entity_id=row.entity_id,
                    subject_employee_id=row.subject_employee_id,
                    action=(
                        QuickAction(
                            kind="unlock_account", label="Blokni ochish", account_id=row.entity_id
                        )
                        if is_open
                        else None
                    ),
                    resolved_at=row.resolved_at,
                    resolved_by=(
                        PersonOut(
                            account_id=row.resolved_by_account_id,
                            name=person(row.resolved_by_account_id),
                        )
                        if row.resolved_by_account_id
                        else None
                    ),
                    resolution=Resolution(row.resolution) if row.resolution else None,
                    resolution_note=row.resolution_note,
                )
            )
        return result
