"""Muammolar (DECISIONS: N-001…N-009).

Bitta qator = bitta OCHIQ muammo. Bir xil muammo takrorlansa yangi qator ochilmaydi —
`occurrences` oshadi (N-002). Bu `group_key` bo'yicha qisman unikal indeks bilan
bazaning o'zida kafolatlanadi: bir kalit bilan bir vaqtda faqat bitta ochiq muammo.
Yopilgan muammo o'chirilmaydi — tarix (N-003).
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProblemType(StrEnum):
    ACCOUNT_LOCKED = "account_locked"  # 10 ta xato parol (A-032) — blok ochilsa o'zi yopiladi


PROBLEM_LABELS: dict[ProblemType, str] = {
    ProblemType.ACCOUNT_LOCKED: "Akkaunt bloklandi",
}


class ProblemStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class Resolution(StrEnum):
    AUTO = "auto"  # sabab bartaraf etildi (masalan, blok ochildi) — o'zi yopildi
    REVIEWED = "reviewed"  # admin qo'lda "Ko'rib chiqildi" (Kassa bosqichida)


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in sorted(values))})"


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(10), server_default=ProblemStatus.OPEN.value)

    # Nimaga oid: ("account", 7). Tezkor tugma shu orqali ishlaydi ("Blokni ochish")
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int] = mapped_column(BigInteger)
    # "Xodim" filtri uchun (N-004). Xodim butunlay o'chirilsa — muammo tarixi qoladi
    subject_employee_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("employees.id", ondelete="SET NULL")
    )

    # Guruhlash kaliti: "account_locked:account:7" (N-002)
    group_key: Mapped[str] = mapped_column(String(100))
    occurrences: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    first_occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # NULL — "Tizim" (masalan, superadmin blokini server buyrug'i ochdi)
    resolved_by_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    resolution: Mapped[str | None] = mapped_column(String(10))
    resolution_note: Mapped[str | None] = mapped_column(String(500))

    # Superadminga oid muammo — admin ko'rmaydi (AU-001 kabi)
    superadmin_only: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))

    __table_args__ = (
        CheckConstraint(_in("type", [t.value for t in ProblemType]), name="type_valid"),
        CheckConstraint(_in("status", [s.value for s in ProblemStatus]), name="status_valid"),
        CheckConstraint(
            "resolution IS NULL OR " + _in("resolution", [r.value for r in Resolution]),
            name="resolution_valid",
        ),
        # Ochiq — yechim maydonlari bo'sh; yopilgan — vaqt va usul albatta bor
        CheckConstraint(
            "(status = 'open') = (resolved_at IS NULL AND resolution IS NULL)",
            name="resolution_fields_match_status",
        ),
        CheckConstraint("occurrences >= 1", name="occurrences_positive"),
        CheckConstraint("last_occurred_at >= first_occurred_at", name="occurred_order"),
        # N-002: bir kalit bilan bitta ochiq muammo
        Index(
            "uq_problems_open_group_key",
            "group_key",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        # Ro'yxat va 🔔 soni: holat bo'yicha, eng yangisi tepada
        Index("ix_problems_status_last", "status", "last_occurred_at"),
        Index("ix_problems_subject_employee", "subject_employee_id"),
    )
