"""Xodimlar va ularning lavozim tarixi (docs/modules/auth.md; DECISIONS: E-001…E-012)."""

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    text,
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
    # +998XXXXXXXXX. NULL faqat anonimlashtirilgan xodimda (E-009)
    phone: Mapped[str | None] = mapped_column(String(13), unique=True)
    # Joriy lavozim va maosh. Tarixi — employee_positions jadvalida (E-010)
    role: Mapped[str] = mapped_column(String(20))
    salary: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    photo_path: Mapped[str | None] = mapped_column(String(255))

    # Arxivlangan: kira olmaydi, lekin istalgan payt qaytarish mumkin (E-005)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # "O'chirilgan", lekin tarixi bor: shaxsiy ma'lumotlar tozalangan (E-009)
    anonymized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(_in_list("gender", Gender), name="gender_valid"),
        CheckConstraint(_in_list("role", EMPLOYEE_ROLES), name="role_valid"),
        CheckConstraint("salary >= 0", name="salary_not_negative"),
        CheckConstraint("phone ~ '^\\+998[0-9]{9}$'", name="phone_format"),
        CheckConstraint("birth_date > '1900-01-01'", name="birth_date_sane"),
        # Telefon va rasm majburiy — faqat anonimlashtirilgan xodimda bo'sh bo'lishi mumkin
        CheckConstraint(
            "anonymized_at IS NOT NULL OR (phone IS NOT NULL AND photo_path IS NOT NULL)",
            name="contacts_required",
        ),
        Index("ix_employees_role", "role"),
        Index("ix_employees_created_at", "created_at"),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class EmployeePosition(Base, TimestampMixin):
    """Lavozim va maosh tarixi — 1C'dagi "kadrlar ko'chirilishi" (E-010).

    Har qator — bitta davr: [valid_from, valid_to]. Ochiq davr (valid_to = NULL) — joriy.
    Oylik shu tarix bo'yicha hisoblanadi: noyabr — kassir maoshi, dekabr — omborchi maoshi.
    """

    __tablename__ = "employee_positions"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("employees.id", ondelete="RESTRICT")
    )
    role: Mapped[str] = mapped_column(String(20))
    salary: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)

    __table_args__ = (
        CheckConstraint(_in_list("role", EMPLOYEE_ROLES), name="role_valid"),
        CheckConstraint("salary >= 0", name="salary_not_negative"),
        CheckConstraint("valid_to IS NULL OR valid_to >= valid_from", name="period_valid"),
        # Har xodimda faqat BITTA joriy (ochiq) lavozim
        Index(
            "uq_employee_positions_one_open",
            "employee_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
        Index("ix_employee_positions_employee_id", "employee_id"),
    )
