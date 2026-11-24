""" "Parollar" bo'limi API sxemalari."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator

from app.core.roles import Role


class AccountState(StrEnum):
    """Ro'yxatdagi holat ustuni."""

    ACTIVE = "active"
    TEMPORARILY_LOCKED = "temporarily_locked"  # 10 daqiqalik blok (Redis)
    LOCKED = "locked"  # doimiy blok — admin ochadi
    DELETED = "deleted"


class AccountStatusFilter(StrEnum):
    ACTIVE = "active"  # o'chirilmaganlar (bloklanganlar ham shu yerda, holati bilan)
    LOCKED = "locked"  # faqat doimiy bloklanganlar
    DELETED = "deleted"


class _NewPassword(BaseModel):
    password: str = Field(max_length=128, json_schema_extra={"format": "password"})
    password_confirm: str = Field(max_length=128, json_schema_extra={"format": "password"})


class AccountCreate(_NewPassword):
    employee_id: int
    username: str = Field(max_length=100, examples=["anvar"])


class PasswordReset(_NewPassword):
    """Yangi parol. Eski parol so'ralmaydi — uni yuqori darajadagi odam beradi (A-017)."""


class UnlockRequest(BaseModel):
    """Blokni ochish sababi majburiy — audit jurnalida saqlanadi (AU-006)."""

    reason: str = Field(min_length=1, max_length=500, examples=["Parolini unutgan, tekshirildi"])

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Sabab bo'sh bo'lmasligi kerak")
        return value


class AccountOut(BaseModel):
    id: int
    username: str
    employee_id: int
    employee_full_name: str
    role: Role
    role_label: str
    state: AccountState
    locked_until: datetime | None = Field(description="Vaqtincha blok qachon tugaydi")
    last_login_at: datetime | None
    created_at: datetime
    deleted_at: datetime | None
