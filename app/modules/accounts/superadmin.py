"""Superadmin'ni yaratish va blokdan ochish — faqat server buyrug'i orqali (A-013, A-019)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.modules.accounts.models import UserAccount
from app.modules.accounts.validation import normalize_username, validate_new_password
from app.modules.audit import service as audit
from app.modules.audit.catalog import AuditAction


async def _get_superadmin(session: AsyncSession) -> UserAccount | None:
    stmt = select(UserAccount).where(UserAccount.is_superadmin.is_(True))
    return (await session.execute(stmt)).scalar_one_or_none()


async def create_superadmin(
    session: AsyncSession, username: str, password: str, confirmation: str
) -> UserAccount:
    if await _get_superadmin(session) is not None:
        raise ConflictError("Superadmin allaqachon mavjud", code="SUPERADMIN_EXISTS")

    clean_username = normalize_username(username)
    taken = await session.execute(
        select(UserAccount.id).where(UserAccount.username == clean_username)
    )
    if taken.first() is not None:
        raise ConflictError("Bu username band", code="USERNAME_TAKEN")

    account = UserAccount(
        username=clean_username,
        password_hash=hash_password(validate_new_password(password, confirmation)),
        is_superadmin=True,
    )
    session.add(account)
    await session.flush()
    await _record(session, AuditAction.ACCOUNT_SUPERADMIN_CREATED, account)
    await session.commit()
    return account


async def unlock_superadmin(session: AsyncSession) -> UserAccount:
    account = await _get_superadmin(session)
    if account is None:
        raise NotFoundError("Superadmin topilmadi")
    account.locked_at = None
    account.failed_attempts = 0
    await _record(session, AuditAction.ACCOUNT_SUPERADMIN_UNLOCKED, account)
    await session.commit()
    return account


async def _record(session: AsyncSession, action: AuditAction, account: UserAccount) -> None:
    """Server buyrug'i — aktyor "Tizim"; admin bu yozuvlarni ko'rmaydi (AU-001)."""
    await audit.record(
        session, actor=None, action=action, entity=("account", account.id), concerns_superadmin=True
    )
