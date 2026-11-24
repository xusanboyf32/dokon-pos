"""Audit jurnaliga yozish (DECISIONS: AU-001…AU-012).

Ishlatish (service ichida, amal bilan BITTA tranzaksiyada — AU-009):

    from app.modules.audit import service as audit

    await audit.record(
        session,
        actor=current_user,                 # None → "Tizim"
        action=AuditAction.EMPLOYEE_SALARY_CHANGED,
        entity=("employee", employee.id),
        changes={"salary": (old_salary, new_salary)},
    )

request_id, IP va brauzer joriy so'rovdan avtomatik olinadi.
Muhimlik katalogdan olinadi — chaqiruvchi bermaydi.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.core.pagination import CursorPage, CursorParams, encode_cursor
from app.core.request_context import current_request
from app.core.roles import Role
from app.modules.accounts import names
from app.modules.audit import repository
from app.modules.audit.catalog import AuditAction, Severity, spec_of
from app.modules.audit.models import AuditEvent
from app.modules.audit.schemas import AuditActorOut, AuditEventOut, AuditFilters
from app.modules.audit.summary import SYSTEM_NAME, build_summary

REASON_MAX_LENGTH = 500

# Bunday kalitli maydonlar jurnalga hech qachon tushmaydi (AU-002)
_SECRET_MARKERS = ("password", "hash", "token", "secret")


class Actor(Protocol):
    """Amalni bajargan foydalanuvchi. `CurrentUser` shu shaklga mos keladi."""

    @property
    def account_id(self) -> int: ...

    @property
    def role(self) -> Role: ...


@dataclass(frozen=True, slots=True)
class ActorRef:
    """`CurrentUser` hali yo'q joylar uchun (masalan, login paytida — aktyor akkauntning o'zi)."""

    account_id: int
    role: Role


class ReasonRequiredError(AppError):
    status_code = 422
    code = "REASON_REQUIRED"
    message = "Bu amal uchun sabab ko'rsatilishi shart"


def _to_json(value: Any) -> Any:
    """Qiymatni JSON'ga aniq va yo'qotishsiz o'giradi."""
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str):
        return value
    if isinstance(value, Decimal):
        return str(value)  # "3500000.00" — tiyin yo'qolmaydi
    if isinstance(value, datetime | date):
        return value.isoformat()
    # float ham shu yerga tushadi: pulni float'da yozish taqiqlangan (D-005)
    raise TypeError(f"Audit uchun qo'llab-quvvatlanmaydigan tur: {type(value).__name__}")


def build_changes(changes: Mapping[str, tuple[Any, Any]] | None) -> dict[str, Any] | None:
    """`{"maydon": (eski, yangi)}` → `{"maydon": [eski, yangi]}`; o'zgarmaganlar tashlanadi."""
    if not changes:
        return None
    result: dict[str, Any] = {}
    for field, (old, new) in changes.items():
        if any(marker in field.lower() for marker in _SECRET_MARKERS):
            raise ValueError(f"Maxfiy maydon audit jurnaliga yozilmaydi: {field!r}")
        old_json, new_json = _to_json(old), _to_json(new)
        if old_json != new_json:
            result[field] = [old_json, new_json]
    return result or None


def _clean_reason(reason: str | None, *, required: bool) -> str | None:
    cleaned = (reason or "").strip() or None
    if cleaned is None and required:
        raise ReasonRequiredError(details={"field": "reason"})
    if cleaned is not None and len(cleaned) > REASON_MAX_LENGTH:
        raise ValueError(f"Sabab {REASON_MAX_LENGTH} belgidan oshmasligi kerak")
    return cleaned


async def record(
    session: AsyncSession,
    *,
    actor: Actor | None,
    action: AuditAction,
    entity: tuple[str, int],
    changes: Mapping[str, tuple[Any, Any]] | None = None,
    reason: str | None = None,
    concerns_superadmin: bool = False,
    kassa_id: int | None = None,
) -> AuditEvent:
    """Bitta audit yozuvini joriy tranzaksiyaga qo'shadi. Commit qilmaydi."""
    spec = spec_of(action)
    entity_type, entity_id = entity
    context = current_request()
    actor_is_superadmin = actor is not None and actor.role == Role.SUPERADMIN

    event = AuditEvent(
        actor_account_id=actor.account_id if actor else None,
        actor_role=actor.role.value if actor else None,
        action=action.value,
        severity=spec.severity.value,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=build_changes(changes),
        reason=_clean_reason(reason, required=spec.reason_required),
        superadmin_only=actor_is_superadmin or concerns_superadmin,
        request_id=context.request_id,
        ip=context.ip,
        user_agent=context.user_agent,
        kassa_id=kassa_id,
    )
    return await repository.add(session, event)


# ================================================================== o'qish (GET /audit-logs)
class AuditService:
    """Jurnalni o'qish. `viewer` — kim ko'ryapti (admin superadmin yozuvlarini ko'rmaydi).

    `CurrentUser` emas, `Actor` turi: auth moduli audit'ni import qiladi, audit esa auth'ni
    import qilsa — aylanma import (circular import) bo'lardi.
    """

    def __init__(self, session: AsyncSession, viewer: Actor) -> None:
        self._session = session
        self._viewer = viewer

    async def search(self, filters: AuditFilters, page: CursorParams) -> CursorPage[AuditEventOut]:
        rows = await repository.search(
            self._session, filters, page, include_superadmin_only=self._sees_superadmin
        )
        return await self._page(rows, page)

    async def employee_history(
        self, employee_id: int, page: CursorParams, *, include_logins: bool = False
    ) -> CursorPage[AuditEventOut]:
        """Xodim kartochkasidagi "Tarix" tabi (AU-019)."""
        if not await repository.employee_exists(self._session, employee_id):
            raise NotFoundError("Xodim topilmadi")
        rows = await repository.employee_history(
            self._session,
            employee_id,
            page,
            include_logins=include_logins,
            include_superadmin_only=self._sees_superadmin,
        )
        return await self._page(rows, page)

    @property
    def _sees_superadmin(self) -> bool:
        return self._viewer.role == Role.SUPERADMIN

    async def _page(self, rows: list[AuditEvent], page: CursorParams) -> CursorPage[AuditEventOut]:
        has_more = len(rows) > page.limit
        rows = rows[: page.limit]
        items = await self._to_out(rows)
        last = rows[-1] if rows and has_more else None
        return CursorPage[AuditEventOut](
            items=items,
            next_cursor=encode_cursor(last.occurred_at, last.id) if last else None,
            has_more=has_more,
        )

    async def _to_out(self, rows: list[AuditEvent]) -> list[AuditEventOut]:
        # Ismlar 2 ta so'rov bilan olinadi — yozuvlar soni qancha bo'lmasin (N+1 yo'q)
        account_ids = {r.actor_account_id for r in rows if r.actor_account_id is not None}
        account_ids |= {r.entity_id for r in rows if r.entity_type == "account"}
        employee_ids = {r.entity_id for r in rows if r.entity_type == "employee"}
        accounts = await names.account_names(self._session, account_ids)
        employees = await names.employee_names(self._session, employee_ids)

        def account_label(account_id: int) -> str:
            info = accounts.get(account_id)
            return info.login_label if info else f"akkaunt #{account_id}"

        def actor_name(account_id: int) -> str:
            info = accounts.get(account_id)
            return info.person if info else f"akkaunt #{account_id}"

        def entity_name(row: AuditEvent) -> str:
            if row.entity_type == "employee":
                return employees.get(row.entity_id, f"O'chirilgan xodim #{row.entity_id}")
            if row.entity_type == "account":
                return account_label(row.entity_id)
            return f"{row.entity_type} #{row.entity_id}"

        result = []
        for row in rows:
            action = AuditAction(row.action)
            label = spec_of(action).label
            who = actor_name(row.actor_account_id) if row.actor_account_id else SYSTEM_NAME
            target = entity_name(row)
            result.append(
                AuditEventOut(
                    id=row.id,
                    occurred_at=row.occurred_at,
                    severity=Severity(row.severity),
                    action=action,
                    action_label=label,
                    actor=(
                        AuditActorOut(
                            account_id=row.actor_account_id,
                            name=who,
                            role=Role(row.actor_role),
                        )
                        if row.actor_account_id is not None and row.actor_role is not None
                        else None
                    ),
                    entity_type=row.entity_type,
                    entity_id=row.entity_id,
                    entity_name=target,
                    changes=row.changes,
                    reason=row.reason,
                    summary=build_summary(
                        actor_name=who,
                        action_label=label,
                        entity_name=target,
                        changes=row.changes,
                        reason=row.reason,
                        self_action=(
                            row.entity_type == "account" and row.entity_id == row.actor_account_id
                        ),
                    ),
                    ip=row.ip,
                )
            )
        return result
