"""EmployeeService: yaratish, qidirish, lavozim tarixi, arxiv, o'chirish (E-009…E-012)."""

import io
import uuid
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.pagination import PageParams
from app.core.roles import Role
from app.modules.accounts.models import UserAccount
from app.modules.auth.exceptions import InvalidCredentialsError
from app.modules.auth.models import RevokeReason
from app.modules.auth.service import AuthService, CurrentUser
from app.modules.employees.models import Employee, EmployeePosition, Gender
from app.modules.employees.photos import InvalidPhotoError
from app.modules.employees.schemas import (
    EmployeeCreate,
    EmployeeStatus,
    EmployeeUpdate,
    PositionChange,
)
from app.modules.employees.service import (
    EmployeeArchivedError,
    EmployeeService,
    InvalidPositionDateError,
    NothingChangedError,
    PhoneTakenError,
    today,
)
from tests.integration.test_auth_service import create_user, login, sessions_of

PAGE = PageParams(page=1, size=20)


# ------------------------------------------------------------------ yordamchilar
def make_photo(size: tuple[int, int] = (64, 64), fmt: str = "PNG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "teal").save(buffer, format=fmt)
    return buffer.getvalue()


def media_file(relative_url: str | None) -> Path:
    assert relative_url is not None
    relative = relative_url.removeprefix(get_settings().media_url.rstrip("/") + "/")
    return Path(get_settings().media_root) / relative


def actor(role: Role) -> CurrentUser:
    return CurrentUser(account_id=0, session_id=uuid.uuid4(), role=role, employee_id=None)


def new_employee(**overrides: object) -> EmployeeCreate:
    data: dict[str, object] = {
        "first_name": "Anvar",
        "last_name": "Karimov",
        "birth_date": "2001-05-12",
        "gender": "male",
        "phone": "90 111 22 33",
        "role": "kassir",
        "salary": "4000000",
    }
    data.update(overrides)
    return EmployeeCreate.model_validate(data)


@pytest.fixture
def admin(db_session: AsyncSession) -> EmployeeService:
    return EmployeeService(db_session, actor(Role.ADMIN))


@pytest.fixture
def boss(db_session: AsyncSession) -> EmployeeService:
    return EmployeeService(db_session, actor(Role.SUPERADMIN))


async def position_rows(session: AsyncSession, employee_id: int) -> list[EmployeePosition]:
    stmt = (
        select(EmployeePosition)
        .where(EmployeePosition.employee_id == employee_id)
        .order_by(EmployeePosition.valid_from)
        .execution_options(populate_existing=True)
    )
    return list((await session.execute(stmt)).scalars())


async def hired(session: AsyncSession, employee_id: int, days_ago: int) -> None:
    """`create_user` xodimiga lavozim davrini qo'shadi: N kun oldin ishga kirgan."""
    session.add(
        EmployeePosition(
            employee_id=employee_id,
            role="kassir",
            salary=Decimal("4000000"),
            valid_from=today() - timedelta(days=days_ago),
        )
    )
    await session.flush()


# ================================================================== yaratish
async def test_create_saves_employee_position_and_photo(
    db_session: AsyncSession, admin: EmployeeService
) -> None:
    out = await admin.create(new_employee(), make_photo())

    assert out.phone == "+998 90 111 22 33"
    assert out.full_name == "Anvar Karimov"
    assert out.role_label
    assert out.status is EmployeeStatus.ACTIVE
    assert out.gender is Gender.MALE
    assert out.age >= 18
    assert media_file(out.photo_url).is_file()
    [position] = await position_rows(db_session, out.id)
    assert position.role == "kassir"
    assert position.salary == Decimal("4000000.00")
    assert position.valid_from == today()
    assert position.valid_to is None


async def test_big_photo_is_shrunk_to_512_jpeg(admin: EmployeeService) -> None:
    out = await admin.create(new_employee(), make_photo((2000, 1000), "JPEG"))

    with Image.open(media_file(out.photo_url)) as saved:
        assert saved.format == "JPEG"
        assert max(saved.size) == 512


@pytest.mark.parametrize("content", [b"", b"bu rasm emas", make_photo(fmt="GIF")])
async def test_invalid_photo_is_rejected_and_nothing_saved(
    db_session: AsyncSession, admin: EmployeeService, content: bytes
) -> None:
    with pytest.raises(InvalidPhotoError):
        await admin.create(new_employee(), content)

    assert await db_session.scalar(select(func.count()).select_from(Employee)) == 0


async def test_phone_must_be_unique(admin: EmployeeService) -> None:
    await admin.create(new_employee(), make_photo())

    with pytest.raises(PhoneTakenError):
        await admin.create(new_employee(phone="+998901112233"), make_photo())


async def test_admin_cannot_create_admin_but_superadmin_can(
    admin: EmployeeService, boss: EmployeeService
) -> None:
    with pytest.raises(ForbiddenError):
        await admin.create(new_employee(role="admin"), make_photo())

    out = await boss.create(new_employee(role="admin"), make_photo())
    assert out.role is Role.ADMIN


@pytest.mark.parametrize("role", ["superadmin", "taminotchi"])
async def test_nobody_can_create_hidden_or_non_employee_roles(
    boss: EmployeeService, role: str
) -> None:
    with pytest.raises(ForbiddenError):
        await boss.create(new_employee(role=role), make_photo())


async def test_low_roles_cannot_manage_employees(db_session: AsyncSession) -> None:
    kassir = EmployeeService(db_session, actor(Role.KASSIR))

    with pytest.raises(ForbiddenError):
        await kassir.create(new_employee(), make_photo())


# ================================================================== qidirish
async def test_search_filters_and_paginates(admin: EmployeeService, boss: EmployeeService) -> None:
    first = await admin.create(new_employee(first_name="Ali", phone="901000001"), make_photo())
    await admin.create(
        new_employee(first_name="Vali", phone="901000002", role="omborchi"), make_photo()
    )
    last = await admin.create(new_employee(first_name="Gani", phone="901000003"), make_photo())
    archived = await admin.create(new_employee(first_name="Soli", phone="901000004"), make_photo())
    await admin.archive(archived.id)

    page = await admin.search(PAGE)
    assert page.total == 3
    assert page.items[0].id == last.id  # oxirgi qo'shilgan birinchi

    small = await admin.search(PageParams(page=2, size=2))
    assert (small.total, small.pages, len(small.items)) == (3, 2, 1)
    assert small.items[0].id == first.id

    kassirs = await admin.search(PAGE, role=Role.KASSIR)
    assert {e.first_name for e in kassirs.items} == {"Ali", "Gani"}

    by_full_name = await admin.search(PAGE, text_query="gani karim")
    assert [e.id for e in by_full_name.items] == [last.id]

    archive = await admin.search(PAGE, status=EmployeeStatus.ARCHIVED)
    assert [e.id for e in archive.items] == [archived.id]

    in_range = await admin.search(PAGE, created_from=today() - timedelta(days=1))
    assert in_range.total == 3
    assert (await admin.search(PAGE, created_to=today() - timedelta(days=1))).total == 0


async def test_like_special_chars_are_literal(admin: EmployeeService) -> None:
    await admin.create(new_employee(first_name="Ali"), make_photo())

    assert (await admin.search(PAGE, text_query="%")).total == 0
    assert (await admin.search(PAGE, text_query="_li")).total == 0


async def test_roles_directory_hides_superadmin_and_counts_active(
    admin: EmployeeService,
) -> None:
    await admin.create(new_employee(phone="901000001"), make_photo())
    archived = await admin.create(new_employee(phone="901000002"), make_photo())
    await admin.archive(archived.id)

    directory = {r.role: r.employee_count for r in await admin.roles_directory()}

    assert Role.SUPERADMIN not in directory
    assert Role.TAMINOTCHI not in directory
    assert directory[Role.KASSIR] == 1
    assert directory[Role.ADMIN] == 0


async def test_unknown_employee_is_not_found(admin: EmployeeService) -> None:
    with pytest.raises(NotFoundError):
        await admin.get(999_999)


# ================================================================== tahrirlash
async def test_update_personal_fields(admin: EmployeeService) -> None:
    out = await admin.create(new_employee(), make_photo())

    updated = await admin.update(
        out.id, EmployeeUpdate(last_name="Valiyev", phone="+998 93 000 00 01")
    )

    assert updated.last_name == "Valiyev"
    assert updated.first_name == "Anvar"  # yuborilmagan maydon o'zgarmaydi
    assert updated.phone == "+998 93 000 00 01"


async def test_update_to_someone_elses_phone_fails(admin: EmployeeService) -> None:
    await admin.create(new_employee(phone="901000001"), make_photo())
    other = await admin.create(new_employee(phone="901000002"), make_photo())

    with pytest.raises(PhoneTakenError):
        await admin.update(other.id, EmployeeUpdate(phone="901000001"))


async def test_admin_cannot_edit_admin(admin: EmployeeService, boss: EmployeeService) -> None:
    other_admin = await boss.create(new_employee(role="admin"), make_photo())

    with pytest.raises(ForbiddenError):
        await admin.update(other_admin.id, EmployeeUpdate(first_name="X"))


async def test_replace_photo_deletes_old_file(admin: EmployeeService) -> None:
    out = await admin.create(new_employee(), make_photo())
    old_file = media_file(out.photo_url)

    updated = await admin.replace_photo(out.id, make_photo((100, 100)))

    assert not old_file.exists()
    assert media_file(updated.photo_url).is_file()


# ================================================================== lavozim tarixi
async def test_role_change_closes_old_period_and_logs_out(
    db_session: AsyncSession, admin: EmployeeService, service: AuthService
) -> None:
    account = await create_user(db_session)  # kassir, login bor
    await login(service)
    await hired(db_session, account.employee_id or 0, days_ago=30)
    start = today() - timedelta(days=30)
    version_before = account.token_version

    change_day = today()
    out = await admin.change_position(
        account.employee_id or 0,
        PositionChange(role=Role.OMBORCHI, salary=Decimal("5000000"), valid_from=change_day),
    )

    assert out.role is Role.OMBORCHI
    old, new = await position_rows(db_session, out.id)
    assert (old.role, old.valid_from, old.valid_to) == ("kassir", start, change_day - timedelta(1))
    assert (new.role, new.valid_from, new.valid_to) == ("omborchi", change_day, None)
    await db_session.refresh(account)
    assert account.token_version == version_before + 1
    [auth_session] = await sessions_of(db_session, account.id)
    assert auth_session.revoked_reason == RevokeReason.ROLE_CHANGED


async def test_salary_change_keeps_sessions(
    db_session: AsyncSession, admin: EmployeeService, service: AuthService
) -> None:
    account = await create_user(db_session)
    await login(service)
    await hired(db_session, account.employee_id or 0, days_ago=10)

    await admin.change_position(
        account.employee_id or 0,
        PositionChange(role=Role.KASSIR, salary=Decimal("4500000"), valid_from=today()),
    )

    assert len(await position_rows(db_session, account.employee_id or 0)) == 2
    [auth_session] = await sessions_of(db_session, account.id)
    assert auth_session.revoked_at is None


async def test_same_day_change_corrects_current_period(
    db_session: AsyncSession, admin: EmployeeService
) -> None:
    out = await admin.create(new_employee(), make_photo())  # davr bugundan

    await admin.change_position(
        out.id, PositionChange(role=Role.KASSIR, salary=Decimal("4200000"), valid_from=today())
    )

    [position] = await position_rows(db_session, out.id)
    assert position.salary == Decimal("4200000.00")


async def test_change_before_current_period_is_rejected(admin: EmployeeService) -> None:
    out = await admin.create(new_employee(), make_photo())

    with pytest.raises(InvalidPositionDateError):
        await admin.change_position(
            out.id,
            PositionChange(
                role=Role.OMBORCHI, salary=Decimal("1"), valid_from=today() - timedelta(days=1)
            ),
        )


async def test_nothing_changed_is_rejected(admin: EmployeeService) -> None:
    out = await admin.create(new_employee(), make_photo())

    with pytest.raises(NothingChangedError):
        await admin.change_position(
            out.id, PositionChange(role=Role.KASSIR, salary=Decimal("4000000"), valid_from=today())
        )


async def test_admin_cannot_promote_to_admin(admin: EmployeeService) -> None:
    out = await admin.create(new_employee(), make_photo())

    with pytest.raises(ForbiddenError):
        await admin.change_position(
            out.id, PositionChange(role=Role.ADMIN, salary=Decimal("1"), valid_from=today())
        )


async def test_archived_employee_position_cannot_change(admin: EmployeeService) -> None:
    out = await admin.create(new_employee(), make_photo())
    await admin.archive(out.id)

    with pytest.raises(EmployeeArchivedError):
        await admin.change_position(
            out.id, PositionChange(role=Role.OMBORCHI, salary=Decimal("1"), valid_from=today())
        )


async def test_positions_history_newest_first(admin: EmployeeService) -> None:
    out = await admin.create(new_employee(), make_photo())

    history = await admin.positions(out.id)

    assert [(p.role, p.valid_to) for p in history] == [(Role.KASSIR, None)]


# ================================================================== arxiv
async def test_archive_disables_login_and_restore_enables(
    db_session: AsyncSession, admin: EmployeeService, service: AuthService
) -> None:
    account = await create_user(db_session)
    await login(service)
    employee_id = account.employee_id or 0

    archived = await admin.archive(employee_id)

    assert archived.status is EmployeeStatus.ARCHIVED
    [auth_session] = await sessions_of(db_session, account.id)
    assert auth_session.revoked_reason == RevokeReason.ACCOUNT_DISABLED
    with pytest.raises(InvalidCredentialsError):
        await login(service)

    restored = await admin.restore(employee_id)

    assert restored.status is EmployeeStatus.ACTIVE
    await login(service)  # o'sha login yana ishlaydi


async def test_archive_and_restore_are_idempotent(admin: EmployeeService) -> None:
    out = await admin.create(new_employee(), make_photo())

    first = await admin.archive(out.id)
    second = await admin.archive(out.id)
    assert first.archived_at == second.archived_at

    await admin.restore(out.id)
    assert (await admin.restore(out.id)).status is EmployeeStatus.ACTIVE


# ================================================================== o'chirish
async def test_delete_without_history_removes_everything(
    db_session: AsyncSession, admin: EmployeeService
) -> None:
    out = await admin.create(new_employee(), make_photo())
    photo = media_file(out.photo_url)

    await admin.delete(out.id)

    assert await db_session.get(Employee, out.id) is None
    assert await position_rows(db_session, out.id) == []
    assert not photo.exists()


async def test_delete_with_history_anonymizes(
    db_session: AsyncSession, admin: EmployeeService, service: AuthService
) -> None:
    account = await create_user(db_session, phone="+998901112233")
    await login(service)
    employee_id = account.employee_id or 0

    await admin.delete(employee_id)

    employee = await db_session.get(Employee, employee_id, populate_existing=True)
    assert employee is not None  # qator qoladi — tarix (sotuvlar, kassa) unga bog'lanadi
    assert employee.first_name == "O'chirilgan"
    assert employee.last_name == f"xodim #{employee_id}"
    assert (employee.phone, employee.photo_path) == (None, None)
    assert employee.anonymized_at is not None
    stored = await db_session.get(UserAccount, account.id, populate_existing=True)
    assert stored is not None and stored.deleted_at is not None
    [auth_session] = await sessions_of(db_session, account.id)
    assert auth_session.revoked_at is not None

    with pytest.raises(NotFoundError):  # hech qayerda ko'rinmaydi
        await admin.get(employee_id)
    assert (await admin.search(PAGE, status=EmployeeStatus.ARCHIVED)).total == 0
    # telefon bo'shadi — yangi xodimga berish mumkin
    await admin.create(new_employee(phone="+998901112233"), make_photo())


async def test_admin_cannot_delete_admin(admin: EmployeeService, boss: EmployeeService) -> None:
    other_admin = await boss.create(new_employee(role="admin"), make_photo())

    with pytest.raises(ForbiddenError):
        await admin.delete(other_admin.id)
