"""Audit jurnali API sxemalari (GET /audit-logs)."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.core.roles import Role
from app.modules.audit.catalog import AuditAction, Severity


class AuditModule(StrEnum):
    """Filtrdagi "Bo'lim": amal nomining birinchi qismi (`employee.salary_changed` → employee)."""

    AUTH = "auth"
    ACCOUNT = "account"
    EMPLOYEE = "employee"


class AuditFilters(BaseModel):
    """Barcha filtrlar birga qo'llanadi (VA). Bo'sh qoldirilgani — cheklov yo'q."""

    date_from: date | None = Field(None, description="Toshkent sanasi bo'yicha, shu kun ham kiradi")
    date_to: date | None = Field(None, description="Toshkent sanasi bo'yicha, shu kun ham kiradi")
    actor_employee_id: int | None = Field(None, description="Kim qildi (xodim)")
    module: AuditModule | None = None
    actions: list[AuditAction] = Field(default_factory=list, description="Bir nechta amal turi")
    min_severity: Severity = Field(Severity.IMPORTANT, description="Standart: important+ (AU-005)")
    entity_type: str | None = Field(None, description="Masalan: employee, account")
    entity_id: int | None = None


class AuditActorOut(BaseModel):
    account_id: int
    name: str = Field(examples=["Ali Valiyev"])
    role: Role = Field(description="Amal paytidagi rol")


class AuditEventOut(BaseModel):
    id: int
    occurred_at: datetime
    severity: Severity
    action: AuditAction
    action_label: str = Field(examples=["Maosh o'zgardi"])
    actor: AuditActorOut | None = Field(description="null — Tizim (avtomatik blok, CLI)")
    entity_type: str
    entity_id: int
    entity_name: str = Field(examples=["Anvar Karimov"])
    changes: dict[str, Any] | None
    reason: str | None
    summary: str = Field(
        examples=["Ali Valiyev: maosh o'zgardi — Anvar Karimov. Maosh: 3 000 000 → 3 500 000"]
    )
    ip: str | None
