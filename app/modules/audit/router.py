"""Audit jurnali endpoint'lari — faqat o'qish (yozish service'lar ichida, AU-009)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.pagination import CursorPage, CursorParams, cursor_params
from app.core.roles import Role
from app.modules.audit.catalog import AuditAction, Severity
from app.modules.audit.schemas import AuditEventOut, AuditFilters, AuditModule
from app.modules.audit.service import AuditService
from app.modules.auth.dependencies import require_roles
from app.modules.auth.service import CurrentUser

router = APIRouter(prefix="/audit-logs", tags=["Audit jurnali"])
# Xodim kartochkasidagi "Tarix" — URL xodimlarniki, mantiq audit modulida
history_router = APIRouter(prefix="/employees", tags=["Xodimlar"])

_admin = require_roles(Role.ADMIN)  # superadmin har doim kiradi (AU-001)


def get_service(
    session: AsyncSession = Depends(get_session), viewer: CurrentUser = Depends(_admin)
) -> AuditService:
    return AuditService(session, viewer)


Service = Annotated[AuditService, Depends(get_service)]
Cursor = Annotated[CursorParams, Depends(cursor_params)]


def audit_filters(
    date_from: date | None = Query(None, description="Toshkent sanasi, shu kun ham kiradi"),
    date_to: date | None = Query(None, description="Toshkent sanasi, shu kun ham kiradi"),
    actor_employee_id: int | None = Query(None, description="Kim qildi (xodim ID)"),
    module: AuditModule | None = Query(None, description="Bo'lim"),
    action: list[AuditAction] = Query(  # noqa: B008
        [], description="Amal turi; bir nechtasi: ?action=a&action=b"
    ),
    min_severity: Severity = Query(Severity.IMPORTANT, description="Standart: important+"),
    entity_type: str | None = Query(None, description="employee, account"),
    entity_id: int | None = Query(None),
) -> AuditFilters:
    return AuditFilters(
        date_from=date_from,
        date_to=date_to,
        actor_employee_id=actor_employee_id,
        module=module,
        actions=action,
        min_severity=min_severity,
        entity_type=entity_type,
        entity_id=entity_id,
    )


@router.get("", response_model=CursorPage[AuditEventOut], summary="Audit jurnali")
async def list_audit_logs(
    service: Service, filters: Annotated[AuditFilters, Depends(audit_filters)], page: Cursor
) -> CursorPage[AuditEventOut]:
    """Eng yangisi tepada. Keyingi sahifa: javobdagi `next_cursor` ni `cursor` ga bering."""
    return await service.search(filters, page)


@history_router.get(
    "/{employee_id}/history", response_model=CursorPage[AuditEventOut], summary="Xodim tarixi"
)
async def employee_history(
    employee_id: int,
    service: Service,
    page: Cursor,
    include_logins: bool = Query(False, description="Tizimga kirishlarni ham ko'rsatish"),
) -> CursorPage[AuditEventOut]:
    """Xodimning o'ziga va uning loginiga oid barcha yozuvlar, eng yangisi tepada (AU-019)."""
    return await service.employee_history(employee_id, page, include_logins=include_logins)
