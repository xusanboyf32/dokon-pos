"""Vaqt bilan ishlash.

Qoida: bazada va kodda vaqt doim UTC, timezone-aware.
Foydalanuvchiga ko'rsatishda Toshkent vaqtiga o'giriladi.
`datetime.now()` / `datetime.utcnow()` to'g'ridan-to'g'ri ishlatilmaydi.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

TASHKENT_TZ = ZoneInfo("Asia/Tashkent")


def utcnow() -> datetime:
    """Hozirgi vaqt, UTC, timezone bilan."""
    return datetime.now(UTC)


def to_tashkent(value: datetime) -> datetime:
    """UTC vaqtni Toshkent vaqtiga o'giradi."""
    if value.tzinfo is None:
        raise ValueError("Timezone'siz datetime qabul qilinmaydi")
    return value.astimezone(TASHKENT_TZ)
