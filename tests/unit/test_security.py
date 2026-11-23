"""Parol hash'i va tokenlar (app/core/security.py)."""

import uuid
from datetime import timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.security import (
    JWT_ALGORITHM,
    AccessTokenClaims,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.core.time import utcnow

CLAIMS = AccessTokenClaims(account_id=7, token_version=3, session_id=uuid.uuid4())


def _secret() -> str:
    return get_settings().jwt_secret_key.get_secret_value()


def _sign(payload: dict[str, object], key: str | None = None) -> str:
    return jwt.encode(payload, key or _secret(), algorithm=JWT_ALGORITHM)


def _valid_payload(**overrides: object) -> dict[str, object]:
    now = utcnow()
    payload: dict[str, object] = {
        "sub": "7",
        "ver": 3,
        "sid": str(CLAIMS.session_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    payload.update(overrides)
    return payload


# ------------------------------------------------------------------ parol
def test_password_hash_is_argon2id_and_not_plain() -> None:
    hashed = hash_password("1234")

    assert hashed.startswith("$argon2id$")
    assert "1234" not in hashed


def test_same_password_gives_different_hashes_but_both_verify() -> None:
    # Har hash'da tasodifiy "tuz" (salt) bor — bir xil parollar bazada bir xil ko'rinmaydi
    first, second = hash_password("1234"), hash_password("1234")

    assert first != second
    assert verify_password("1234", first)
    assert verify_password("1234", second)


@pytest.mark.parametrize("wrong", ["12345", "123", "", " 1234"])
def test_wrong_password_is_rejected(wrong: str) -> None:
    assert not verify_password(wrong, hash_password("1234"))


def test_password_is_case_sensitive() -> None:
    assert not verify_password("parol", hash_password("Parol"))  # A-017


# ------------------------------------------------------------------ access token
def test_access_token_roundtrip() -> None:
    assert decode_access_token(create_access_token(CLAIMS)) == CLAIMS


def test_access_token_contains_no_secrets() -> None:
    payload = jwt.decode(create_access_token(CLAIMS), options={"verify_signature": False})

    assert set(payload) == {"sub", "ver", "sid", "type", "iat", "exp"}


def _assert_rejected(token: str, code: str) -> None:
    with pytest.raises(UnauthorizedError) as error:
        decode_access_token(token)
    assert error.value.code == code


def test_expired_token_is_rejected() -> None:
    past = utcnow() - timedelta(minutes=16)
    token = _sign(_valid_payload(iat=past, exp=past + timedelta(minutes=15)))

    _assert_rejected(token, "TOKEN_EXPIRED")


def test_tampered_token_is_rejected() -> None:
    token = create_access_token(CLAIMS)
    header, payload, signature = token.split(".")
    forged_payload = jwt.utils.base64url_encode(b'{"sub":"1","ver":0}').decode()

    _assert_rejected(f"{header}.{forged_payload}.{signature}", "INVALID_TOKEN")


def test_token_signed_with_other_key_is_rejected() -> None:
    _assert_rejected(_sign(_valid_payload(), key="x" * 48), "INVALID_TOKEN")


def test_unsigned_alg_none_token_is_rejected() -> None:
    token = jwt.encode(_valid_payload(), key=None, algorithm="none")

    _assert_rejected(token, "INVALID_TOKEN")


@pytest.mark.parametrize("missing", ["sub", "ver", "sid", "type", "exp"])
def test_token_without_required_claim_is_rejected(missing: str) -> None:
    payload = _valid_payload()
    del payload[missing]

    _assert_rejected(_sign(payload), "INVALID_TOKEN")


def test_non_access_token_type_is_rejected() -> None:
    _assert_rejected(_sign(_valid_payload(type="refresh")), "INVALID_TOKEN")


def test_garbage_is_rejected() -> None:
    _assert_rejected("bu-token-emas", "INVALID_TOKEN")


# ------------------------------------------------------------------ refresh token
def test_refresh_tokens_are_random_and_long() -> None:
    tokens = {generate_refresh_token() for _ in range(100)}

    assert len(tokens) == 100
    assert all(len(t) >= 43 for t in tokens)  # 32 bayt = 256 bit


def test_refresh_token_hash_is_deterministic_sha256() -> None:
    token = generate_refresh_token()

    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert len(hash_refresh_token(token)) == 64
    assert hash_refresh_token(token) != token
