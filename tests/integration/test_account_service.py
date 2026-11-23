"""AccountService: "Parollar" bo'limi — yaratish, parol almashtirish, blok, o'chirish."""

import uuid

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.pagination import PageParams
from app.core.roles import Role
from app.core.time import utcnow
from app.modules.accounts.models import UserAccount
from app.modules.accounts.schemas import (
    AccountCreate,
    AccountState,
    AccountStatusFilter,
    PasswordReset,
)
from app.modules.accounts.service import (
    AccountDeletedError,
    AccountExistsError,
    AccountService,
    UsernameTakenError,
)
from app.modules.accounts.superadmin import create_superadmin
from app.modules.accounts.validation import (
    InvalidPasswordError,
    InvalidUsernameError,
    PasswordMismatchError,
)
from app.modules.auth.exceptions import AccountLockedError, InvalidCredentialsError
from app.modules.auth.lockout import LoginGuard
from app.modules.auth.models import RevokeReason
from app.modules.auth.service import AuthService, CurrentUser
from app.modules.employees.models import Employee
from app.modules.employees.service import EmployeeArchivedError
from tests.integration.test_auth_service import CLIENT, PASSWORD, create_user, login, sessions_of
from tests.integration.test_employees_table import make_employee

PAGE = PageParams(page=1, size=20)
NEW = "yangi123"


def actor(role: Role) -> CurrentUser:
    return CurrentUser(account_id=0, session_id=uuid.uuid4(), role=role, employee_id=None)


@pytest.fixture
def admin(db_session: AsyncSession, guard: LoginGuard) -> AccountService:
    return AccountService(db_session, actor(Role.ADMIN), guard)


@pytest.fixture
def boss(db_session: AsyncSession, guard: LoginGuard) -> AccountService:
    return AccountService(db_session, actor(Role.SUPERADMIN), guard)


async def add_employee(
    session: AsyncSession, *, role: str = "kassir", phone: str = "+998905555555", **kw: object
) -> Employee:
    employee = make_employee(role=role, phone=phone, **kw)
    session.add(employee)
    await session.flush()
    return employee


def new_login(employee_id: int, username: str = "vali", password: str = NEW) -> AccountCreate:
    return AccountCreate(
        employee_id=employee_id, username=username, password=password, password_confirm=password
    )


def new_password(password: str = NEW, confirm: str | None = None) -> PasswordReset:
    return PasswordReset(password=password, password_confirm=confirm or password)


# ================================================================== yaratish
async def test_create_login_and_sign_in(
    db_session: AsyncSession, admin: AccountService, service: AuthService
) -> None:
    employee = await add_employee(db_session)

    out = await admin.create(new_login(employee.id, username="  Vali.K "))

    assert out.username == "vali.k"  # kichik harf, bo'sh joysiz (A-016)
    assert out.state is AccountState.ACTIVE
    assert out.role is Role.KASSIR
    assert out.employee_full_name == employee.full_name
    pair = await service.login("vali.k", NEW, **CLIENT)
    assert pair.role is Role.KASSIR


@pytest.mark.parametrize(
    ("data", "error"),
    [
        ({"username": "ab"}, InvalidUsernameError),
        ({"username": "vali karim"}, InvalidUsernameError),
        ({"password": "123"}, InvalidPasswordError),
    ],
)
async def test_create_validates_username_and_password(
    db_session: AsyncSession,
    admin: AccountService,
    data: dict[str, str],
    error: type[Exception],
) -> None:
    employee = await add_employee(db_session)

    with pytest.raises(error):
        await admin.create(new_login(employee.id, **data))


async def test_create_requires_matching_confirmation(
    db_session: AsyncSession, admin: AccountService
) -> None:
    employee = await add_employee(db_session)
    data = AccountCreate(
        employee_id=employee.id, username="vali", password=NEW, password_confirm="boshqa1"
    )

    with pytest.raises(PasswordMismatchError):
        await admin.create(data)


async def test_one_active_login_per_employee(
    db_session: AsyncSession, admin: AccountService
) -> None:
    employee = await add_employee(db_session)
    await admin.create(new_login(employee.id))

    with pytest.raises(AccountExistsError):
        await admin.create(new_login(employee.id, username="vali2"))


async def test_deleted_username_is_never_reused(
    db_session: AsyncSession, admin: AccountService
) -> None:
    employee = await add_employee(db_session)
    first = await admin.create(new_login(employee.id))
    await admin.delete(first.id)

    with pytest.raises(UsernameTakenError):  # A-010
        await admin.create(new_login(employee.id, username="VALI"))

    second = await admin.create(new_login(employee.id, username="vali2"))  # 3A: yangi login
    assert second.state is AccountState.ACTIVE


async def test_archived_employee_gets_no_login(
    db_session: AsyncSession, admin: AccountService
) -> None:
    employee = await add_employee(db_session, archived_at=utcnow())

    with pytest.raises(EmployeeArchivedError):  # 2A
        await admin.create(new_login(employee.id))


async def test_unknown_employee(admin: AccountService) -> None:
    with pytest.raises(NotFoundError):
        await admin.create(new_login(999_999))


async def test_admin_cannot_create_login_for_admin(
    db_session: AsyncSession, admin: AccountService, boss: AccountService
) -> None:
    employee = await add_employee(db_session, role="admin")

    with pytest.raises(ForbiddenError):
        await admin.create(new_login(employee.id))

    out = await boss.create(new_login(employee.id))
    assert out.role is Role.ADMIN


# ================================================================== ro'yxat
async def test_list_shows_states_and_hides_superadmin(
    db_session: AsyncSession, admin: AccountService, guard: LoginGuard
) -> None:
    await create_superadmin(db_session, "xusanboy", "1234", "1234")
    active = await create_user(db_session, username="faol", phone="+998901000001")
    temp = await create_user(db_session, username="vaqtincha", phone="+998901000002")
    perm = await create_user(db_session, username="doimiy", phone="+998901000003")
    gone = await create_user(db_session, username="ketgan", phone="+998901000004")
    perm.locked_at = utcnow()
    gone.deleted_at = utcnow()
    await db_session.flush()
    await guard.lock_temporarily("vaqtincha")

    page = await admin.search(PAGE)

    states = {a.username: a.state for a in page.items}
    assert states == {
        "faol": AccountState.ACTIVE,
        "vaqtincha": AccountState.TEMPORARILY_LOCKED,
        "doimiy": AccountState.LOCKED,
    }
    [temp_out] = [a for a in page.items if a.id == temp.id]
    assert temp_out.locked_until is not None
    assert [a.id for a in (await admin.search(PAGE, status=AccountStatusFilter.LOCKED)).items] == [
        perm.id
    ]
    deleted = await admin.search(PAGE, status=AccountStatusFilter.DELETED)
    assert [a.id for a in deleted.items] == [gone.id]
    assert active.id in {a.id for a in page.items}


async def test_list_search_and_role_filter(db_session: AsyncSession, admin: AccountService) -> None:
    await create_user(db_session, username="anvar", phone="+998901000001")
    await create_user(db_session, username="sklad", role=Role.OMBORCHI, phone="+998901000002")

    by_username = await admin.search(PAGE, text_query="skl")
    assert [a.username for a in by_username.items] == ["sklad"]
    by_name = await admin.search(PAGE, text_query="anvar karimov")  # make_employee ismi
    assert by_name.total == 2
    kassirs = await admin.search(PAGE, role=Role.KASSIR)
    assert [a.username for a in kassirs.items] == ["anvar"]


async def test_list_survives_redis_outage(db_session: AsyncSession) -> None:
    await create_user(db_session)
    dead_redis = Redis.from_url("redis://localhost:1/0", socket_connect_timeout=0.2)
    try:
        service = AccountService(db_session, actor(Role.ADMIN), LoginGuard(dead_redis))
        page = await service.search(PAGE)
    finally:
        await dead_redis.aclose()

    assert page.items[0].state is AccountState.ACTIVE  # fail-open: ro'yxat baribir ochiladi


async def test_superadmin_account_is_not_found(
    db_session: AsyncSession, boss: AccountService
) -> None:
    account = await create_superadmin(db_session, "xusanboy", "1234", "1234")

    with pytest.raises(NotFoundError):
        await boss.get(account.id)


# ================================================================== parol almashtirish
async def test_reset_password_logs_out_everywhere(
    db_session: AsyncSession, admin: AccountService, service: AuthService
) -> None:
    account = await create_user(db_session)
    await login(service)
    version = account.token_version

    await admin.reset_password(account.id, new_password())

    await db_session.refresh(account)
    assert account.token_version == version + 1
    [auth_session] = await sessions_of(db_session, account.id)
    assert auth_session.revoked_reason == RevokeReason.PASSWORD_CHANGED
    with pytest.raises(InvalidCredentialsError):
        await login(service)  # eski parol endi ishlamaydi
    await service.login("anvar", NEW, **CLIENT)


async def test_reset_password_mismatch(db_session: AsyncSession, admin: AccountService) -> None:
    account = await create_user(db_session)

    with pytest.raises(PasswordMismatchError):
        await admin.reset_password(account.id, new_password(NEW, "boshqa1"))


async def test_admin_cannot_reset_admin_password(
    db_session: AsyncSession, admin: AccountService, boss: AccountService
) -> None:
    other_admin = await create_user(db_session, username="admin2", role=Role.ADMIN)

    with pytest.raises(ForbiddenError):
        await admin.reset_password(other_admin.id, new_password())

    await boss.reset_password(other_admin.id, new_password())


async def test_deleted_login_password_cannot_be_reset(
    db_session: AsyncSession, admin: AccountService
) -> None:
    account = await create_user(db_session)
    await admin.delete(account.id)

    with pytest.raises(AccountDeletedError):
        await admin.reset_password(account.id, new_password())


# ================================================================== blokni ochish
async def test_unlock_permanent_and_temporary_lock(
    db_session: AsyncSession, admin: AccountService, guard: LoginGuard, service: AuthService
) -> None:
    account = await create_user(db_session)
    account.locked_at = utcnow()
    await db_session.flush()
    await guard.lock_temporarily("anvar")
    with pytest.raises(AccountLockedError):
        await service.login("anvar", PASSWORD, **CLIENT)

    out = await admin.unlock(account.id)

    assert out.state is AccountState.ACTIVE
    assert await guard.locked_seconds_left(["anvar"]) == {}
    await login(service)


async def test_admin_cannot_unlock_admin(
    db_session: AsyncSession, admin: AccountService, boss: AccountService
) -> None:
    other_admin = await create_user(db_session, username="admin2", role=Role.ADMIN)
    other_admin.locked_at = utcnow()
    await db_session.flush()

    with pytest.raises(ForbiddenError):
        await admin.unlock(other_admin.id)

    assert (await boss.unlock(other_admin.id)).state is AccountState.ACTIVE


# ================================================================== o'chirish
async def test_delete_login_keeps_employee(
    db_session: AsyncSession, admin: AccountService, service: AuthService
) -> None:
    account = await create_user(db_session)
    await login(service)

    await admin.delete(account.id)
    await admin.delete(account.id)  # takror — xato emas

    stored = await db_session.get(UserAccount, account.id, populate_existing=True)
    assert stored is not None and stored.deleted_at is not None
    assert await db_session.get(Employee, account.employee_id) is not None
    [auth_session] = await sessions_of(db_session, account.id)
    assert auth_session.revoked_reason == RevokeReason.ACCOUNT_DISABLED
    with pytest.raises(InvalidCredentialsError):
        await login(service)
    assert (await admin.get(account.id)).state is AccountState.DELETED
