"""Audit jurnali (docs/modules/audit.md → audit_events).

Faqat qo'shiladi: UPDATE, DELETE, TRUNCATE baza triggeri bilan taqiqlangan (AU-010).
Shuning uchun `updated_at` yo'q va TimestampMixin ishlatilmaydi.

O'zbekcha matn bu yerda saqlanmaydi — o'qish paytida `action` + `changes` + ismlardan
yig'iladi. Ismlar `employee_id` orqali olinadi, nusxalanmaydi (E-006).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.roles import Role
from app.modules.audit.catalog import Severity

# `modul.amal`: kichik lotin harflar va `_` (AU-008). Ro'yxatning o'zi kodda — catalog.py
ACTION_PATTERN = "^[a-z][a-z_]*\\.[a-z][a-z_]*$"


def _in(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in sorted(values))})"


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    # now() — tranzaksiya boshlangan vaqt: bitta amaldagi yozuvlar bir xil vaqtda bo'ladi
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Kim. NULL = "Tizim" (avtomatik blok, CLI buyrug'i)
    actor_account_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    # Amal paytidagi rol. Keyin lavozimi o'zgarsa ham shu qoladi
    actor_role: Mapped[str | None] = mapped_column(String(20))

    action: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(10))

    # Nimaga nisbatan: ("employee", 12), ("account", 7)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int] = mapped_column(BigInteger)

    # {"maydon": [eski, yangi]} — faqat o'zgarganlar (AU-002). Pul matn sifatida, float emas
    # none_as_null=True: Python None → SQL NULL. Aks holda JSON 'null' qiymati yoziladi
    # va "changes IS NULL" filtri uni topmaydi
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    reason: Mapped[str | None] = mapped_column(String(500))

    # Superadminning amali yoki superadminga oid yozuv — admin ko'rmaydi (AU-001)
    superadmin_only: Mapped[bool] = mapped_column(Boolean)

    request_id: Mapped[str | None] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    # Kassa jadvali 7-bosqichda paydo bo'ladi — FK o'shanda qo'shiladi
    kassa_id: Mapped[int | None] = mapped_column(BigInteger)

    __table_args__ = (
        CheckConstraint(f"action ~ '{ACTION_PATTERN}'", name="action_format"),
        CheckConstraint(_in("severity", [s.value for s in Severity]), name="severity_valid"),
        CheckConstraint(_in("actor_role", [r.value for r in Role]), name="actor_role_valid"),
        # Rol faqat aktyor bor bo'lsa yoziladi, aktyor bo'lsa — albatta
        CheckConstraint(
            "(actor_account_id IS NULL) = (actor_role IS NULL)", name="actor_fields_together"
        ),
        CheckConstraint("entity_type ~ '^[a-z][a-z_]*$'", name="entity_type_format"),
        CheckConstraint("reason IS NULL OR btrim(reason) <> ''", name="reason_not_blank"),
        CheckConstraint(
            "changes IS NULL OR jsonb_typeof(changes) = 'object'", name="changes_is_object"
        ),
        # Umumiy ro'yxat va keyset pagination (eng yangisi tepada)
        Index("ix_audit_events_occurred", "occurred_at", "id"),
        # Ob'ekt tarixi: xodim kartochkasidagi "Tarix" tabi
        Index("ix_audit_events_entity", "entity_type", "entity_id", "occurred_at"),
        # "Bu odam nima qildi?"
        Index("ix_audit_events_actor", "actor_account_id", "occurred_at"),
    )
