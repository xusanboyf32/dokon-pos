"""Sessiyalar — har bir kirish (docs/modules/auth.md → auth_sessions).

Bir login = bitta sessiya qatori. Refresh qilinganda eski qator "rotated" bo'lib yopiladi
va xuddi shu `family_id` bilan yangi qator ochiladi. Shuning uchun bir oila — bitta
kirishning butun tarixi. Yopilgan token qayta ishlatilsa — o'g'irlik belgisi (A-006).
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class RevokeReason(StrEnum):
    LOGOUT = "logout"  # foydalanuvchi o'zi chiqdi
    ROTATED = "rotated"  # refresh qilindi, o'rniga yangisi ochildi
    PASSWORD_CHANGED = "password_changed"
    ROLE_CHANGED = "role_changed"
    REUSE_DETECTED = "reuse_detected"  # yopilgan token qayta ishlatildi → o'g'irlik
    NEW_LOGIN = "new_login"  # kassir boshqa joydan kirdi (A-014)
    ADMIN = "admin"  # admin majburan chiqardi
    ACCOUNT_DISABLED = "account_disabled"  # login o'chirildi / xodim arxivlandi / blok


def _reason_check() -> str:
    values = ", ".join(f"'{r.value}'" for r in sorted(RevokeReason, key=lambda r: r.value))
    return f"revoked_reason IN ({values})"


class AuthSession(Base, TimestampMixin):
    __tablename__ = "auth_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("user_accounts.id", ondelete="RESTRICT")
    )
    # Bitta logindan boshlangan zanjir: login → refresh → refresh → ...
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)

    # Tokenning o'zi emas — faqat SHA-256 hash'i (64 belgi)
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)

    ip: Mapped[str | None] = mapped_column(String(45))  # IPv6 ham sig'adi
    user_agent: Mapped[str | None] = mapped_column(String(255))

    # Login + 24 soat. Rotation'da yangi qatorga AYNAN SHU qiymat ko'chiriladi (A-005)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_reason: Mapped[str | None] = mapped_column(String(30))

    __table_args__ = (
        CheckConstraint(_reason_check(), name="revoked_reason_valid"),
        # Yopilgan bo'lsa — sababi ham bo'lishi shart, va aksincha
        CheckConstraint(
            "(revoked_at IS NULL) = (revoked_reason IS NULL)", name="revoked_fields_together"
        ),
        CheckConstraint("absolute_expires_at > created_at", name="expires_after_created"),
        # "Shu akkauntning faol sessiyalari" — eng ko'p ishlatiladigan so'rov
        Index(
            "ix_auth_sessions_account_active",
            "account_id",
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None
