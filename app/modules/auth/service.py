"""Auth biznes-mantig'i: login, refresh, logout, joriy foydalanuvchi.

Oqimlar docs/modules/auth.md, 4-bo'limda. Har bir ochiq metod — bitta tranzaksiya.
Kirishga urinishdan himoya: 10 ta ketma-ket xato → blok, hisoblagich bazada (A-032).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.roles import Role
from app.core.security import (
    AccessTokenClaims,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
    verify_password_against_dummy,
)
from app.core.time import utcnow
from app.modules.accounts.models import UserAccount
from app.modules.audit import service as audit
from app.modules.audit.catalog import AuditAction
from app.modules.auth import repository as repo
from app.modules.auth.exceptions import (
    AccountLockedError,
    InvalidCredentialsError,
    RefreshTokenReusedError,
    SessionExpiredError,
    SessionInvalidError,
)
from app.modules.auth.models import AuthSession, RevokeReason

log = structlog.get_logger()

# Bir vaqtda faqat bitta joyda ishlay oladigan rollar (A-014)
SINGLE_SESSION_ROLES = frozenset({Role.KASSIR})


@dataclass(frozen=True, slots=True)
class TokenPair:
    access_token: str
    refresh_token: str
    refresh_expires_at: datetime
    role: Role


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Har so'rovda aniqlanadigan "kim bu?" ma'lumoti."""

    account_id: int
    session_id: uuid.UUID
    role: Role
    employee_id: int | None


def resolve_role(account: UserAccount) -> Role:
    """Rol akkauntda saqlanmaydi — egasidan olinadi (E-006)."""
    if account.is_superadmin:
        return Role.SUPERADMIN
    if account.employee is not None:
        return Role(account.employee.role)
    return Role.TAMINOTCHI  # ta'minotchi akkauntlari (5-bosqich)


def _can_sign_in(account: UserAccount) -> bool:
    """Login o'chirilmagan va xodim arxivlanmagan (24, 21-bandlar)."""
    if account.deleted_at is not None:
        return False
    return account.employee is None or account.employee.archived_at is None


# A-032: shuncha ketma-ket xato parol — akkaunt bloklanadi, faqat admin/superadmin ochadi
MAX_FAILED_ATTEMPTS = 10


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------ login
    async def login(
        self, username: str, password: str, *, ip: str | None, user_agent: str | None
    ) -> TokenPair:
        username = username.strip().lower()
        account = await repo.get_account_by_username(self._session, username)

        # 1. Bloklangan — to'g'ri parol ham qabul qilinmaydi (A-032)
        if account is not None and account.locked_at is not None:
            verify_password_against_dummy(password)  # javob vaqti bir xil bo'lsin
            raise AccountLockedError()

        # 2. Parol. Akkaunt topilmasa ham soxta hash tekshiriladi — javob vaqtidan
        #    qaysi username mavjudligini bilib bo'lmasin.
        if account is None or not _can_sign_in(account):
            verify_password_against_dummy(password)
            raise InvalidCredentialsError()
        if not verify_password(password, account.password_hash):
            await self._register_failure(account, username, ip)
            raise InvalidCredentialsError()

        # 3. Muvaffaqiyat — hisoblagich 0
        account.failed_attempts = 0
        now = utcnow()
        role = resolve_role(account)
        if role in SINGLE_SESSION_ROLES:
            await repo.revoke_active_sessions_of_account(
                self._session, account.id, RevokeReason.NEW_LOGIN, now
            )

        refresh_token = generate_refresh_token()
        auth_session = AuthSession(
            id=uuid.uuid4(),
            account_id=account.id,
            family_id=uuid.uuid4(),
            refresh_token_hash=hash_refresh_token(refresh_token),
            ip=ip,
            user_agent=(user_agent or "")[:255] or None,
            absolute_expires_at=now + timedelta(hours=get_settings().refresh_token_hours),
        )
        repo.add_session(self._session, auth_session)
        account.last_login_at = now
        await audit.record(
            self._session,
            actor=audit.ActorRef(account.id, role),
            action=AuditAction.AUTH_LOGIN_SUCCESS,
            entity=("account", account.id),
        )
        await self._session.commit()

        return self._token_pair(account, auth_session, refresh_token, role)

    async def _register_failure(self, account: UserAccount, username: str, ip: str | None) -> None:
        """Xato parol: hisoblagich +1; chegaraga yetsa — blok, jurnal va xato (A-032).

        Har bir xato urinish jurnalga yozilmaydi — faqat logga (AU-004). Jurnalga faqat blok.
        Faol sessiyalar TO'XTATILMAYDI — blok faqat yangi kirishga tegadi.
        """
        failures = await repo.register_failed_attempt(self._session, account.id)
        if failures < MAX_FAILED_ATTEMPTS:
            await self._session.commit()
            log.info("login_failed", username=username, ip=ip, failures=failures)
            return

        account.locked_at = utcnow()
        await audit.record(
            self._session,
            actor=None,  # "Tizim"
            action=AuditAction.AUTH_LOCKED_PERMANENT,
            entity=("account", account.id),
            concerns_superadmin=account.is_superadmin,
        )
        await self._session.commit()
        log.warning("account_locked", username=username, ip=ip)
        raise AccountLockedError()

    # ------------------------------------------------------------------ refresh
    async def refresh(
        self, refresh_token: str, *, ip: str | None, user_agent: str | None
    ) -> TokenPair:
        old = await repo.get_session_by_refresh_hash_for_update(
            self._session, hash_refresh_token(refresh_token)
        )
        if old is None:
            raise SessionInvalidError()

        now = utcnow()
        if old.revoked_at is not None:
            if old.revoked_reason == RevokeReason.ROTATED:
                # Allaqachon almashtirilgan token qayta keldi → u o'g'irlangan.
                # Butun oila yopiladi: o'g'ri ham, egasi ham chiqariladi (A-006).
                await repo.revoke_active_sessions_of_family(
                    self._session, old.family_id, RevokeReason.REUSE_DETECTED, now
                )
                victim = await repo.get_account_by_id(self._session, old.account_id)
                await audit.record(
                    self._session,
                    actor=None,
                    action=AuditAction.AUTH_TOKEN_REUSE_DETECTED,
                    entity=("account", old.account_id),
                    concerns_superadmin=victim is not None and victim.is_superadmin,
                )
                await self._session.commit()
                raise RefreshTokenReusedError()
            raise SessionInvalidError()

        if old.absolute_expires_at <= now:
            raise SessionExpiredError()

        account = await repo.get_account_by_id(self._session, old.account_id)
        if account is None or not _can_sign_in(account):
            await repo.revoke_active_sessions_of_family(
                self._session, old.family_id, RevokeReason.ACCOUNT_DISABLED, now
            )
            await self._session.commit()
            raise SessionInvalidError()

        old.revoked_at = now
        old.revoked_reason = RevokeReason.ROTATED
        new_refresh_token = generate_refresh_token()
        new = AuthSession(
            id=uuid.uuid4(),
            account_id=account.id,
            family_id=old.family_id,  # o'sha kirish zanjiri davom etadi
            refresh_token_hash=hash_refresh_token(new_refresh_token),
            ip=ip,
            user_agent=(user_agent or "")[:255] or None,
            absolute_expires_at=old.absolute_expires_at,  # muddat UZAYMAYDI (A-005)
        )
        repo.add_session(self._session, new)
        await self._session.commit()

        return self._token_pair(account, new, new_refresh_token, resolve_role(account))

    # ------------------------------------------------------------------ logout
    async def logout(self, session_id: uuid.UUID) -> None:
        auth_session = await repo.get_session_by_id(self._session, session_id)
        if auth_session is not None and auth_session.revoked_at is None:
            auth_session.revoked_at = utcnow()
            auth_session.revoked_reason = RevokeReason.LOGOUT
            await self._session.commit()

    # ------------------------------------------------------------------ har so'rov
    async def authenticate(self, access_token: str) -> CurrentUser:
        """Access token → kim? Har so'rovda chaqiriladi.

        Token imzosidan tashqari BAZA ham tekshiriladi — shuning uchun parol/rol
        o'zgarishi, logout, arxivlash KEYINGI so'rovdayoq kuchga kiradi (8-band).
        """
        claims = decode_access_token(access_token)

        account = await repo.get_account_by_id(self._session, claims.account_id)
        # locked_at bu yerda tekshirilmaydi: blok faqat yangi kirishga tegadi (7g)
        if (
            account is None
            or not _can_sign_in(account)
            or account.token_version != claims.token_version
        ):
            raise SessionInvalidError()

        auth_session = await repo.get_session_by_id(self._session, claims.session_id)
        if (
            auth_session is None
            or auth_session.revoked_at is not None
            or auth_session.account_id != account.id
        ):
            raise SessionInvalidError()

        return CurrentUser(
            account_id=account.id,
            session_id=auth_session.id,
            role=resolve_role(account),
            employee_id=account.employee_id,
        )

    # ------------------------------------------------------------------ yordamchi
    @staticmethod
    def _token_pair(
        account: UserAccount, auth_session: AuthSession, refresh_token: str, role: Role
    ) -> TokenPair:
        access_token = create_access_token(
            AccessTokenClaims(
                account_id=account.id,
                token_version=account.token_version,
                session_id=auth_session.id,
            )
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            refresh_expires_at=auth_session.absolute_expires_at,
            role=role,
        )
