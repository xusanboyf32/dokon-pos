"""Redis ulanishi.

Redis faqat vaqtinchalik ma'lumot uchun: login hisoblagichlari, keyinchalik Celery navbati.
Qoldiq, narx, pul kabi biznes ma'lumotlari Redis'da SAQLANMAYDI (D-007).
"""

from redis.asyncio import Redis

from app.core.config import get_settings

_client: Redis | None = None


def get_redis() -> Redis:
    """FastAPI dependency. Butun ilova uchun bitta ulanishlar havzasi."""
    global _client
    if _client is None:
        _client = Redis.from_url(
            str(get_settings().redis_url),
            decode_responses=True,
            # Redis javob bermasa — tez taslim bo'lamiz (fail-open, qarang: LoginGuard)
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
