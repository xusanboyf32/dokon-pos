""" "Parollar" bo'limi biznes-mantig'i (docs/modules/auth.md; DECISIONS: A-010, A-011, A-017).

Ruxsat qoidasi xodimlardagi bilan bitta: akkauntning roli = xodimning lavozimi,
foydalanuvchi faqat o'zidan PAST darajadagi akkauntni boshqaradi (`can_manage`).
Admin boshqa admin'ning (o'zining ham) parolini o'zgartira olmaydi — buni superadmin qiladi.
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.pagination import Page, PageParams
from app.core.roles import ROLE_LABELS, Role, can_manage
from app.core.security import hash_password
from app.core.time import utcnow
from app.modules.accounts import repository as repo
from app.modules.accounts.models import UserAccount
from app.modules.accounts.schemas import (
    AccountCreate,
    AccountOut,
    AccountState,
    AccountStatusFilter,
    PasswordReset,
)
from app.modules.accounts.validation import normalize_username, validate_new_password
from app.modules.audit import service as audit
from app.modules.audit.catalog import AuditAction
from app.modules.auth import repository as auth_repo
from app.modules.auth.models import RevokeReason
from app.modules.auth.service import CurrentUser
from app.modules.employees import repository as employees_repo
from app.modules.employees.service import EmployeeArchivedError
from app.modules.problems import service as problems


class UsernameTakenError(ConflictError):
    code = "USERNAME_TAKEN"
    message = "Bu username band (o'chirilgan loginlar nomi ham qayta berilmaydi)"


class AccountExistsError(ConflictError):
    code = "ACCOUNT_EXISTS"
    message = "Bu xodimning faol logini bor. Parolni almashtiring yoki avval loginni o'chiring"


class AccountDeletedError(AppError):
    code = "ACCOUNT_DELETED"
    message = "Login o'chirilgan. Kerak bo'lsa, xodimga yangi login yarating"


def _state(account: UserAccount) -> AccountState:
    if account.deleted_at is not None:
        return AccountState.DELETED
    if account.locked_at is not None:
        return AccountState.LOCKED
    return AccountState.ACTIVE


def to_out(account: UserAccount) -> AccountOut:
    employee = account.employee
    assert employee is not None  # _visible() faqat xodim akkauntlarini qaytaradi
    role = Role(employee.role)
    state = _state(account)
    return AccountOut(
        id=account.id,
        username=account.username,
        employee_id=employee.id,
        employee_full_name=employee.full_name,
        role=role,
        role_label=ROLE_LABELS[role],
        state=state,
        failed_attempts=account.failed_attempts,
        last_login_at=account.last_login_at,
        created_at=account.created_at,
        deleted_at=account.deleted_at,
    )


class AccountService:
    def __init__(self, session: AsyncSession, actor: CurrentUser) -> None:
        self._session = session
        self._actor = actor

    # ------------------------------------------------------------------ yordamchi
    def _require_manage(self, role: Role | str) -> None:
        if not can_manage(self._actor.role, Role(role)):
            raise ForbiddenError("Bu lavozimdagi xodimning loginini boshqarishga ruxsatingiz yo'q")

    async def _get(self, account_id: int) -> UserAccount:
        account = await repo.get(self._session, account_id)
        if account is None:
            raise NotFoundError("Login topilmadi")
        return account

    async def _get_manageable(self, account_id: int) -> UserAccount:
        account = await self._get(account_id)
        assert account.employee is not None
        self._require_manage(account.employee.role)
        return account

    async def _record(
        self,
        action: AuditAction,
        account: UserAccount,
        *,
        changes: dict[str, tuple[object, object]] | None = None,
        reason: str | None = None,
    ) -> None:
        await audit.record(
            self._session,
            actor=self._actor,
            action=action,
            entity=("account", account.id),
            changes=changes,
            reason=reason,
        )

    async def _out(self, account: UserAccount) -> AccountOut:
        return to_out(account)

    # ------------------------------------------------------------------ o'qish
    async def search(
        self,
        params: PageParams,
        *,
        status: AccountStatusFilter = AccountStatusFilter.ACTIVE,
        text_query: str | None = None,
        role: Role | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
    ) -> Page[AccountOut]:
        accounts, total = await repo.search(
            self._session,
            params,
            status=status,
            text_query=text_query,
            role=role,
            created_from=created_from,
            created_to=created_to,
        )
        items = [to_out(a) for a in accounts]
        return Page[AccountOut].build(items, total, params)

    async def get(self, account_id: int) -> AccountOut:
        return await self._out(await self._get(account_id))

    # ------------------------------------------------------------------ yaratish
    async def create(self, data: AccountCreate) -> AccountOut:
        employee = await employees_repo.get(self._session, data.employee_id)
        if employee is None:
            raise NotFoundError("Xodim topilmadi")
        self._require_manage(employee.role)
        if employee.archived_at is not None:
            raise EmployeeArchivedError()  # avval arxivdan qaytarish kerak

        username = normalize_username(data.username)
        password = validate_new_password(data.password, data.password_confirm)
        if await repo.has_active_account(self._session, employee.id):
            raise AccountExistsError()
        if await repo.username_taken(self._session, username):
            raise UsernameTakenError()

        account = UserAccount(
            employee_id=employee.id, username=username, password_hash=hash_password(password)
        )
        self._session.add(account)
        await self._session.flush()  # account.id kerak
        await self._record(
            AuditAction.ACCOUNT_CREATED,
            account,
            changes={"username": (None, username), "employee_id": (None, employee.id)},
        )
        await self._session.commit()
        return await self.get(account.id)

    # ------------------------------------------------------------------ amallar
    async def reset_password(self, account_id: int, data: PasswordReset) -> AccountOut:
        """Yangi parol → eski tokenlar yaroqsiz, xodim hamma qurilmadan chiqadi (A-007)."""
        account = await self._get_manageable(account_id)
        if account.deleted_at is not None:
            raise AccountDeletedError()
        password = validate_new_password(data.password, data.password_confirm)

        account.password_hash = hash_password(password)
        account.token_version += 1
        await auth_repo.revoke_active_sessions_of_account(
            self._session, account.id, RevokeReason.PASSWORD_CHANGED, utcnow()
        )
        await self._record(AuditAction.ACCOUNT_PASSWORD_RESET, account)  # parolning o'zi — yo'q
        await self._session.commit()
        return await self._out(account)

    async def unlock(self, account_id: int, *, reason: str) -> AccountOut:
        """Blok ochiladi va xato urinishlar hisoblagichi 0 ga tushadi (A-032)."""
        account = await self._get_manageable(account_id)
        if account.deleted_at is not None:
            raise AccountDeletedError()
        was_locked = account.locked_at is not None
        account.locked_at = None
        account.failed_attempts = 0
        await self._record(
            AuditAction.ACCOUNT_UNLOCKED,
            account,
            changes={"permanently_locked": (was_locked, False)},
            reason=reason,
        )
        await problems.resolve_account_locked(self._session, account.id, self._actor)  # N-003
        await self._session.commit()
        return await self._out(account)

    async def delete(self, account_id: int) -> None:
        """Login o'chadi, xodim va tarix qoladi. Qaytarib bo'lmaydi — faqat yangi login (A-010)."""
        account = await self._get_manageable(account_id)
        if account.deleted_at is not None:
            return  # takroriy so'rov — natija baribir bir xil
        now = utcnow()
        account.deleted_at = now
        account.token_version += 1
        await auth_repo.revoke_active_sessions_of_account(
            self._session, account.id, RevokeReason.ACCOUNT_DISABLED, now
        )
        await self._record(AuditAction.ACCOUNT_DELETED, account)
        await self._session.commit()
