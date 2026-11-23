"""Akkauntlar — "Xodimlar parollari" bo'limi (docs/modules/auth.md → user_accounts).

Har bir akkaunt AYNAN BITTA egaga tegishli:
  - xodimga (employee_id), yoki
  - ta'minotchiga (supplier_id — 5-bosqichda qo'shiladi), yoki
  - superadmin'ga (is_superadmin = true, hech qaysi jadvalga bog'lanmaydi).
Rol akkauntda saqlanmaydi: xodimning lavozimidan olinadi (E-006 — nusxa yo'q).
"""

from datetime import datetime

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
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin
from app.modules.employees.models import Employee

USERNAME_PATTERN = "^[a-z0-9_.]{3,50}$"


class UserAccount(Base, TimestampMixin):
    __tablename__ = "user_accounts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)

    employee_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("employees.id", ondelete="RESTRICT")
    )
    is_superadmin: Mapped[bool] = mapped_column(Boolean, server_default=false())

    # Doim kichik harfda saqlanadi → "Ahmad" va "ahmad" bitta username (A-016).
    # UNIQUE o'chirilgan akkauntlarga ham amal qiladi → username qayta ishlatilmaydi (A-010).
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    # Parol yoki lavozim o'zgarsa +1 → eski tokenlar yaroqsiz bo'ladi (A-007)
    token_version: Mapped[int] = mapped_column(Integer, server_default=text("0"))

    # Doimiy blok (A-011). Vaqtinchalik 10 daqiqalik blok Redis'da turadi.
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # "Parol o'chirildi" — xodim qoladi, lekin kira olmaydi (spetsifikatsiya, 24-band)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # lazy="raise": xodimni oldindan yuklamasdan murojaat qilinsa — xato.
    # Bu N+1 so'rovlarni (100 akkaunt → 101 so'rov) kod yozilayotgandayoq ushlaydi.
    employee: Mapped[Employee | None] = relationship(lazy="raise")

    __table_args__ = (
        # Aynan bitta ega. num_nonnulls — PostgreSQL funksiyasi: NULL bo'lmaganlar soni.
        CheckConstraint(
            "num_nonnulls(employee_id) + is_superadmin::int = 1",
            name="exactly_one_owner",
        ),
        CheckConstraint(f"username ~ '{USERNAME_PATTERN}'", name="username_format"),
        CheckConstraint("token_version >= 0", name="token_version_not_negative"),
        # Superadmin butun tizimda faqat bitta (R-003)
        Index(
            "uq_user_accounts_single_superadmin",
            "is_superadmin",
            unique=True,
            postgresql_where=text("is_superadmin"),
        ),
        # Bitta xodimga bitta FAOL login (23-band). O'chirilgan login hisobga olinmaydi —
        # shuning uchun "qayta parol berish" yangi login bilan mumkin.
        Index(
            "uq_user_accounts_employee_active",
            "employee_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    @property
    def is_active(self) -> bool:
        return self.deleted_at is None and self.locked_at is None
