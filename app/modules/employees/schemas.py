"""Xodimlar API sxemalari."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.core.money import Money
from app.core.roles import Role
from app.core.time import to_tashkent, utcnow
from app.modules.employees.models import Gender
from app.modules.employees.phone import InvalidPhoneError, normalize_phone

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class EmployeeStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


def _phone(value: str) -> str:
    # Pydantic faqat ValueError'ni maydon xatosi deb biladi → 422 VALIDATION_ERROR
    try:
        return normalize_phone(value)
    except InvalidPhoneError as exc:
        raise ValueError(exc.message) from exc


MIN_AGE = 5
MAX_AGE = 100


def full_years(birth: date, on: date) -> int:
    """To'liq yillar: tug'ilgan kun hali kelmagan bo'lsa — bir yil kam."""
    return on.year - birth.year - ((on.month, on.day) < (birth.month, birth.day))


def _birth_date(value: date) -> date:
    age = full_years(value, to_tashkent(utcnow()).date())
    if not MIN_AGE <= age <= MAX_AGE:
        raise ValueError(f"Xodimning yoshi {MIN_AGE} dan {MAX_AGE} gacha bo'lishi kerak")
    return value


class _PersonalFields(BaseModel):
    first_name: Name
    last_name: Name
    birth_date: date
    gender: Gender
    phone: str = Field(examples=["90 002 12 21"])

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str) -> str:
        return _phone(value)

    @field_validator("birth_date")
    @classmethod
    def _birth_date_in_past(cls, value: date) -> date:
        return _birth_date(value)


class EmployeeCreate(_PersonalFields):
    """Yangi xodim — hamma maydon majburiy (E-001). Rasm alohida fayl sifatida keladi."""

    role: Role
    salary: Money


class EmployeeUpdate(BaseModel):
    """Shaxsiy ma'lumotlarni tahrirlash. Lavozim/maosh — alohida amal (lavozim o'zgarishi)."""

    first_name: Name | None = None
    last_name: Name | None = None
    birth_date: date | None = None
    gender: Gender | None = None
    phone: str | None = None

    @field_validator("phone")
    @classmethod
    def _normalize_phone(cls, value: str | None) -> str | None:
        return None if value is None else _phone(value)

    @field_validator("birth_date")
    @classmethod
    def _birth_date_in_past(cls, value: date | None) -> date | None:
        return None if value is None else _birth_date(value)


class PositionChange(BaseModel):
    role: Role
    salary: Money
    valid_from: date = Field(description="Qaysi sanadan kuchga kiradi")


class EmployeeOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    full_name: str
    birth_date: date
    age: int
    gender: Gender
    phone: str | None = Field(examples=["+998 90 002 12 21"])
    role: Role
    role_label: str
    salary: Decimal
    photo_url: str | None
    status: EmployeeStatus
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PositionOut(BaseModel):
    role: Role
    role_label: str
    salary: Decimal
    valid_from: date
    valid_to: date | None


class RoleOut(BaseModel):
    """Lavozimlar ma'lumotnomasi (E-007)."""

    role: Role
    label: str
    employee_count: int
