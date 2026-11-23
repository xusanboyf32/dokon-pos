"""Parol va tokenlar xavfsizligi (docs/modules/auth.md; DECISIONS: A-004…A-008).

Parol   → argon2id hash (bir tomonlama, qaytarib bo'lmaydi)
Access  → JWT, HS256, 15 daqiqa. Ichida faqat ID'lar — maxfiy ma'lumot yo'q.
Refresh → tasodifiy 256-bit satr; bazada faqat uning SHA-256 hash'i saqlanadi.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.time import utcnow

JWT_ALGORITHM = "HS256"
_REQUIRED_CLAIMS = ["sub", "ver", "sid", "type", "iat", "exp"]

# pwdlib "recommended" = argon2id, OWASP tavsiya qilgan parametrlar bilan
_password_hasher = PasswordHash.recommended()

# Akkaunt topilmaganda ham parol "tekshiriladi" — javob vaqti bir xil bo'lishi uchun.
# Aks holda hujumchi javob tezligidan qaysi username mavjudligini bilib oladi.
_DUMMY_HASH = _password_hasher.hash("timing-attack-protection")


# ------------------------------------------------------------------ parol
def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hasher.verify(password, password_hash)


def verify_password_against_dummy(password: str) -> None:
    """Username topilmaganda chaqiriladi: xuddi haqiqiy tekshiruvdek vaqt sarflaydi."""
    _password_hasher.verify(password, _DUMMY_HASH)


# ------------------------------------------------------------------ access token
@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    account_id: int
    token_version: int
    session_id: uuid.UUID


def create_access_token(claims: AccessTokenClaims) -> str:
    settings = get_settings()
    now = utcnow()
    payload = {
        "sub": str(claims.account_id),  # JWT standarti: sub — satr
        "ver": claims.token_version,
        "sid": str(claims.session_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key.get_secret_value(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> AccessTokenClaims:
    """Imzo, muddat va tarkibni tekshiradi. Xato bo'lsa — 401."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            # Algoritm ANIQ ko'rsatiladi: "alg": "none" hujumining oldini oladi
            algorithms=[JWT_ALGORITHM],
            options={"require": _REQUIRED_CLAIMS},
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Sessiya muddati tugadi", code="TOKEN_EXPIRED") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Token yaroqsiz", code="INVALID_TOKEN") from exc

    if payload["type"] != "access":
        raise UnauthorizedError("Token yaroqsiz", code="INVALID_TOKEN")
    try:
        return AccessTokenClaims(
            account_id=int(payload["sub"]),
            token_version=int(payload["ver"]),
            session_id=uuid.UUID(payload["sid"]),
        )
    except (TypeError, ValueError) as exc:
        raise UnauthorizedError("Token yaroqsiz", code="INVALID_TOKEN") from exc


# ------------------------------------------------------------------ refresh token
def generate_refresh_token() -> str:
    """256 bit tasodifiy satr. Faqat klientga (cookie) beriladi, bazaga YOZILMAYDI."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """Bazada shu saqlanadi. Baza o'g'irlansa ham haqiqiy tokenni tiklab bo'lmaydi.

    argon2 emas, SHA-256: token butunlay tasodifiy (256 bit), uni taxmin qilib
    topish imkonsiz — sekin hash kerak emas, tez qidiruv esa kerak.
    """
    return hashlib.sha256(token.encode()).hexdigest()
