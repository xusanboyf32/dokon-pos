"""Xodimlar jadvali (docs/modules/auth.md → employees; DECISIONS: E-001…E-006)."""

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Identity,
    Index,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin
from app.core.roles import EMPLOYEE_ROLES


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"


def _in_list(column: str, values: Iterable[StrEnum]) -> str:
    """CHECK uchun: column IN ('a', 'b', ...). Qiymatlar enum'dan olinadi — yagona manba."""
    items = ", ".join(f"'{v.value}'" for v in sorted(values, key=lambda x: x.value))
    return f"{column} IN ({items})"


class Employee(Base, TimestampMixin):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    birth_date: Mapped[date] = mapped_column(Date)
    gender: Mapped[str] = mapped_column(String(10))
    # +998XXXXXXXXX — har doim bir xil formatda saqlanadi, aks holda "unikal" ishlamaydi
    phone: Mapped[str] = mapped_column(String(13), unique=True)
    role: Mapped[str] = mapped_column(String(20))
    salary: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    photo_path: Mapped[str] = mapped_column(String(255))

    # Arxivlangan bo'lsa — vaqti; faol bo'lsa — NULL (E-005)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(_in_list("gender", Gender), name="gender_valid"),
        CheckConstraint(_in_list("role", EMPLOYEE_ROLES), name="role_valid"),
        CheckConstraint("salary >= 0", name="salary_not_negative"),
        CheckConstraint("phone ~ '^\\+998[0-9]{9}$'", name="phone_format"),
        CheckConstraint("birth_date > '1900-01-01'", name="birth_date_sane"),
        # Ro'yxat filtrlari uchun: rol bo'yicha, sana bo'yicha (standart tartib — oxirgisi birinchi)
        Index("ix_employees_role", "role"),
        Index("ix_employees_created_at", "created_at"),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
