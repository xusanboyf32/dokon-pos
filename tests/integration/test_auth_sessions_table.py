"""`auth_sessions` jadvalidagi qoidalarni bazaning o'zi kafolatlashini tekshiradi."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_refresh_token, hash_refresh_token
from app.core.time import utcnow
from app.modules.accounts.models import UserAccount
from app.modules.auth.models import AuthSession, RevokeReason
from tests.integration.test_user_accounts_table import FAKE_HASH, create_employee


async def create_account(session: AsyncSession) -> UserAccount:
    employee = await create_employee(session)
    account = UserAccount(employee_id=employee.id, username="anvar", password_hash=FAKE_HASH)
    session.add(account)
    await session.flush()
    return account


def make_session(account_id: int, **overrides: Any) -> AuthSession:
    data: dict[str, Any] = {
        "account_id": account_id,
        "family_id": uuid.uuid4(),
        "refresh_token_hash": hash_refresh_token(generate_refresh_token()),
        "ip": "192.168.1.10",
        "user_agent": "Mozilla/5.0",
        "absolute_expires_at": utcnow() + timedelta(hours=24),
    }
    data.update(overrides)
    return AuthSession(**data)


async def test_session_is_saved(db_session: AsyncSession) -> None:
    account = await create_account(db_session)
    auth_session = make_session(account.id)
    db_session.add(auth_session)
    await db_session.flush()
    await db_session.refresh(auth_session)

    assert isinstance(auth_session.id, uuid.UUID)
    assert not auth_session.is_revoked


async def test_revoked_session_with_reason_is_saved(db_session: AsyncSession) -> None:
    account = await create_account(db_session)
    db_session.add(
        make_session(account.id, revoked_at=utcnow(), revoked_reason=RevokeReason.LOGOUT)
    )

    await db_session.flush()


async def test_refresh_token_hash_is_unique(db_session: AsyncSession) -> None:
    account = await create_account(db_session)
    same_hash = hash_refresh_token("bir-xil-token")
    db_session.add(make_session(account.id, refresh_token_hash=same_hash))
    await db_session.flush()

    db_session.add(make_session(account.id, refresh_token_hash=same_hash))
    with pytest.raises(IntegrityError, match="uq_auth_sessions_refresh_token_hash"):
        await db_session.flush()


@pytest.mark.parametrize(
    "overrides",
    [
        {"revoked_at": utcnow()},  # sababsiz yopilgan
        {"revoked_reason": RevokeReason.LOGOUT},  # sababi bor, vaqti yo'q
    ],
)
async def test_revoked_fields_must_be_set_together(
    db_session: AsyncSession, overrides: dict[str, Any]
) -> None:
    account = await create_account(db_session)
    db_session.add(make_session(account.id, **overrides))

    with pytest.raises(IntegrityError, match="ck_auth_sessions_revoked_fields_together"):
        await db_session.flush()


async def test_unknown_revoke_reason_is_rejected(db_session: AsyncSession) -> None:
    account = await create_account(db_session)
    db_session.add(make_session(account.id, revoked_at=utcnow(), revoked_reason="charchadim"))

    with pytest.raises(IntegrityError, match="ck_auth_sessions_revoked_reason_valid"):
        await db_session.flush()


async def test_session_cannot_expire_before_it_is_created(db_session: AsyncSession) -> None:
    account = await create_account(db_session)
    db_session.add(make_session(account.id, absolute_expires_at=utcnow() - timedelta(hours=1)))

    with pytest.raises(IntegrityError, match="ck_auth_sessions_expires_after_created"):
        await db_session.flush()


async def test_session_requires_existing_account(db_session: AsyncSession) -> None:
    db_session.add(make_session(account_id=999_999))

    with pytest.raises(IntegrityError, match="fk_auth_sessions_account_id_user_accounts"):
        await db_session.flush()
