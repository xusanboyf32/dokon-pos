"""Kirishga urinishdan himoya (spetsifikatsiya 7-band; DECISIONS: A-011, A-018, A-019).

Qoidalar (har username uchun alohida):
  a) 5 ta ketma-ket xato YOKI 1 daqiqada 5 tadan ko'p urinish → 10 daqiqa vaqtincha blok.
     Blok paytidagi urinishlar hisoblanmaydi va blokni uzaytirmaydi.
  b) Blokdan keyin "sinov davri": 3 ta xato yoki yana tezkor urinishlar → DOIMIY blok.
  c) To'g'ri kirilsa — hamma hisoblagich 0.

Saqlash joyi (gibrid):
  - vaqtinchalik hisoblagichlar va 10 daqiqalik blok → Redis (TTL bilan o'zi o'chadi)
  - doimiy blok → PostgreSQL (user_accounts.locked_at) — buni AuthService qiladi

Redis ishlamasa → FAIL-OPEN: himoya vaqtincha o'chadi, do'kon ishlashda davom etadi,
logga ogohlantirish yoziladi. Doimiy bloklar bazada bo'lgani uchun baribir ishlaydi.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError

log = structlog.get_logger()


class LockDecision(StrEnum):
    NONE = "none"
    TEMPORARY = "temporary"  # 10 daqiqa
    PERMANENT = "permanent"  # admin ochmaguncha


@dataclass(frozen=True, slots=True)
class LockoutPolicy:
    max_failures: int = 5
    probation_failures: int = 3
    rate_limit: int = 5  # bir oynada shundan KO'P urinish — buzilish
    rate_window_seconds: int = 60
    lock_seconds: int = 600
    # Blokdan keyingi sinov davri qancha "eslab qolinadi"
    probation_seconds: int = 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class AttemptResult:
    locked_seconds_left: int | None = None  # hozir vaqtincha blokda bo'lsa
    decision: LockDecision = LockDecision.NONE  # tezkor urinishlar tufayli blok


class LoginGuard:
    def __init__(self, redis: Redis, policy: LockoutPolicy | None = None) -> None:
        self._redis = redis
        self._policy = policy or LockoutPolicy()

    # ------------------------------------------------------------------ kalitlar
    @staticmethod
    def _key(kind: str, username: str) -> str:
        return f"auth:{kind}:{username}"

    def _keys(self, username: str) -> tuple[str, str, str, str]:
        return (
            self._key("lock", username),
            self._key("fail", username),
            self._key("rate", username),
            self._key("probation", username),
        )

    # ------------------------------------------------------------------ ochiq API
    async def on_attempt(self, username: str) -> AttemptResult:
        """Har urinish boshida: blokdami? Tezlik chegarasi oshdimi?"""
        lock_key, _, rate_key, _ = self._keys(username)
        try:
            ttl = await self._redis.ttl(lock_key)
            if ttl > 0:
                return AttemptResult(locked_seconds_left=ttl)  # hisoblanmaydi (7a)

            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(rate_key)
                pipe.expire(rate_key, self._policy.rate_window_seconds, nx=True)
                attempts, _ = await pipe.execute()

            if attempts > self._policy.rate_limit:
                return AttemptResult(decision=await self._trip(username))
            return AttemptResult()
        except RedisError:
            log.warning("login_guard_unavailable", step="on_attempt")
            return AttemptResult()

    async def on_failure(self, username: str) -> LockDecision:
        _, fail_key, _, probation_key = self._keys(username)
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.incr(fail_key)
                pipe.expire(fail_key, self._policy.probation_seconds)
                pipe.exists(probation_key)
                failures, _, in_probation = await pipe.execute()

            limit = self._policy.probation_failures if in_probation else self._policy.max_failures
            if failures >= limit:
                return await self._trip(username)
            return LockDecision.NONE
        except RedisError:
            log.warning("login_guard_unavailable", step="on_failure")
            return LockDecision.NONE

    async def on_success(self, username: str) -> None:
        await self.reset(username)

    async def reset(self, username: str) -> None:
        """To'g'ri kirish yoki admin blokni ochganda — hamma hisoblagich 0 (7c, 7e)."""
        try:
            await self._redis.delete(*self._keys(username))
        except RedisError:
            log.warning("login_guard_unavailable", step="reset")

    async def lock_temporarily(self, username: str) -> None:
        """Mavjud bo'lmagan username "doimiy" bloklanolmaydi — u yana vaqtincha bloklanadi."""
        lock_key, fail_key, rate_key, _ = self._keys(username)
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.set(lock_key, "1", ex=self._policy.lock_seconds)
                pipe.delete(fail_key, rate_key)
                await pipe.execute()
        except RedisError:
            log.warning("login_guard_unavailable", step="lock_temporarily")

    async def locked_seconds_left(self, usernames: Sequence[str]) -> dict[str, int]:
        """ "Parollar" ro'yxati uchun: qaysi username vaqtincha blokda va yana necha soniya.

        Bitta pipeline — 20 ta akkaunt uchun 20 ta emas, bitta Redis so'rovi.
        Redis ishlamasa — bo'sh javob (ro'yxat baribir ochiladi).
        """
        if not usernames:
            return {}
        try:
            async with self._redis.pipeline(transaction=False) as pipe:
                for username in usernames:
                    pipe.ttl(self._key("lock", username))
                ttls = await pipe.execute()
        except RedisError:
            log.warning("login_guard_unavailable", step="locked_seconds_left")
            return {}
        return {name: ttl for name, ttl in zip(usernames, ttls, strict=True) if ttl > 0}

    @property
    def lock_seconds(self) -> int:
        return self._policy.lock_seconds

    # ------------------------------------------------------------------ ichki
    async def _trip(self, username: str) -> LockDecision:
        """Chegaradan oshildi: birinchi marta — vaqtincha, sinov davrida — doimiy."""
        lock_key, fail_key, rate_key, probation_key = self._keys(username)
        if await self._redis.exists(probation_key):
            await self._redis.delete(fail_key, rate_key, probation_key)
            return LockDecision.PERMANENT

        async with self._redis.pipeline(transaction=True) as pipe:
            pipe.set(lock_key, "1", ex=self._policy.lock_seconds)
            pipe.set(probation_key, "1", ex=self._policy.probation_seconds)
            pipe.delete(fail_key, rate_key)
            await pipe.execute()
        return LockDecision.TEMPORARY
