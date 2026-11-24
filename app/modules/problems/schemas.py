"""Muammolar API sxemalari."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.modules.problems.models import ProblemStatus, ProblemType, Resolution


class ProblemStatusFilter(StrEnum):
    OPEN = "open"  # standart (N-004)
    RESOLVED = "resolved"
    ALL = "all"


class QuickAction(BaseModel):
    """Muammo yonidagi tugma (N-008): frontend qaysi amalni chaqirishini biladi."""

    kind: str = Field(examples=["unlock_account"])
    label: str = Field(examples=["Blokni ochish"])
    account_id: int | None = None


class PersonOut(BaseModel):
    account_id: int
    name: str


class ProblemOut(BaseModel):
    id: int
    type: ProblemType
    type_label: str = Field(examples=["Akkaunt bloklandi"])
    status: ProblemStatus
    title: str = Field(examples=["login «anvar» (Anvar Karimov) bloklandi"])
    occurrences: int = Field(description="Necha marta takrorlangan (N-002)")
    first_occurred_at: datetime
    last_occurred_at: datetime
    entity_type: str
    entity_id: int
    subject_employee_id: int | None
    action: QuickAction | None = Field(description="Ochiq muammo uchun tezkor tugma")
    resolved_at: datetime | None
    resolved_by: PersonOut | None = Field(description="null — Tizim yoki hali ochiq")
    resolution: Resolution | None
    resolution_note: str | None


class ProblemCountOut(BaseModel):
    open: int = Field(description="🔔 belgisidagi raqam — ochiq muammolar soni (N-001)")
