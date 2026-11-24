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

from app.core.exceptions import AppError
from app.core.request_context import current_request
from app.core.roles import Role
from app.modules.audit import repository
from app.modules.audit.catalog import AuditAction, spec_of
from app.modules.audit.models import AuditEvent

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
