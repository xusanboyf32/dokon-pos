"""Auth uchun bazaga so'rovlar. Bu yerda biznes-qoida YO'Q — faqat SQL."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.modules.accounts.models import UserAccount
from app.modules.auth.models import AuthSession, RevokeReason


async def get_account_by_username(session: AsyncSession, username: str) -> UserAccount | None:
    # joinedload: xodim ma'lumoti BIR so'rovda birga keladi (lazy="raise" talab qiladi)
    stmt = (
        select(UserAccount)
        .options(joinedload(UserAccount.employee))
        .where(UserAccount.username == username)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_account_by_id(session: AsyncSession, account_id: int) -> UserAccount | None:
    stmt = (
        select(UserAccount)
        .options(joinedload(UserAccount.employee))
        .where(UserAccount.id == account_id)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_session_by_id(session: AsyncSession, session_id: uuid.UUID) -> AuthSession | None:
    return await session.get(AuthSession, session_id)


async def get_session_by_refresh_hash_for_update(
    session: AsyncSession, refresh_token_hash: str
) -> AuthSession | None:
    """SELECT ... FOR UPDATE: bir token bilan parallel kelgan ikkita refresh
    navbatma-navbat bajariladi — ikkalasi bir vaqtda "yangi" token ololmaydi."""
    stmt = (
        select(AuthSession)
        .where(AuthSession.refresh_token_hash == refresh_token_hash)
        .with_for_update()
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def add_session(session: AsyncSession, auth_session: AuthSession) -> None:
    session.add(auth_session)


async def revoke_active_sessions_of_account(
    session: AsyncSession, account_id: int, reason: RevokeReason, now: datetime
) -> None:
    stmt = (
        update(AuthSession)
        .where(AuthSession.account_id == account_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now, revoked_reason=reason)
    )
    await session.execute(stmt)


async def revoke_active_sessions_of_family(
    session: AsyncSession, family_id: uuid.UUID, reason: RevokeReason, now: datetime
) -> None:
    stmt = (
        update(AuthSession)
        .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now, revoked_reason=reason)
    )
    await session.execute(stmt)
