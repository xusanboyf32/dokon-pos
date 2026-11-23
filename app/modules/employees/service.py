"""Xodimlar biznes-mantig'i (docs/modules/auth.md; DECISIONS: E-001…E-012, R-005).

Ruxsat qoidasi hamma joyda bitta: foydalanuvchi faqat o'zidan PAST darajadagi
lavozimni boshqaradi (`can_manage`). Admin admin'ni yarata ham, o'zgartira ham olmaydi.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.pagination import Page, PageParams
from app.core.roles import EMPLOYEE_ROLES, ROLE_LABELS, Role, can_manage
from app.core.time import to_tashkent, utcnow
from app.modules.auth import repository as auth_repo
from app.modules.auth.models import RevokeReason
from app.modules.auth.service import CurrentUser
from app.modules.employees import photos
from app.modules.employees import repository as repo
from app.modules.employees.models import Employee, EmployeePosition, Gender
from app.modules.employees.phone import format_phone
from app.modules.employees.schemas import (
    EmployeeCreate,
    EmployeeOut,
    EmployeeStatus,
    EmployeeUpdate,
    PositionChange,
    PositionOut,
    RoleOut,
    full_years,
)


class PhoneTakenError(ConflictError):
    code = "PHONE_TAKEN"
    message = "Bu telefon raqami boshqa xodimga tegishli"


class NothingChangedError(AppError):
    code = "NOTHING_CHANGED"
    message = "Lavozim ham, maosh ham o'zgarmagan"


class InvalidPositionDateError(AppError):
    code = "INVALID_POSITION_DATE"
    message = "Yangi lavozim sanasi joriy lavozim boshlangan sanadan oldin bo'lishi mumkin emas"


class EmployeeArchivedError(AppError):
    code = "EMPLOYEE_ARCHIVED"
    message = "Xodim arxivda. Avval arxivdan qaytaring"


def today() -> date:
    return to_tashkent(utcnow()).date()


def to_out(employee: Employee) -> EmployeeOut:
    role = Role(employee.role)
    return EmployeeOut(
        id=employee.id,
        first_name=employee.first_name,
        last_name=employee.last_name,
        full_name=employee.full_name,
        birth_date=employee.birth_date,
        age=full_years(employee.birth_date, today()),
        gender=Gender(employee.gender),
        phone=format_phone(employee.phone) if employee.phone else None,
        role=role,
        role_label=ROLE_LABELS[role],
        salary=employee.salary,
        photo_url=photos.photo_url(employee.photo_path),
        status=EmployeeStatus.ARCHIVED if employee.archived_at else EmployeeStatus.ACTIVE,
        archived_at=employee.archived_at,
        created_at=employee.created_at,
        updated_at=employee.updated_at,
    )


class EmployeeService:
    def __init__(self, session: AsyncSession, actor: CurrentUser) -> None:
        self._session = session
        self._actor = actor

    # ------------------------------------------------------------------ ruxsat
    def _require_manage(self, role: Role | str) -> None:
        if not can_manage(self._actor.role, Role(role)):
            raise ForbiddenError("Bu lavozimdagi xodimni boshqarishga ruxsatingiz yo'q")

    async def _get(self, employee_id: int) -> Employee:
        employee = await repo.get(self._session, employee_id)
        if employee is None:
            raise NotFoundError("Xodim topilmadi")
        return employee

    async def _ensure_phone_free(self, phone: str, exclude_id: int | None = None) -> None:
        if await repo.phone_taken(self._session, phone, exclude_id):
            raise PhoneTakenError()

    # ------------------------------------------------------------------ o'qish
    async def search(
        self,
        params: PageParams,
        *,
        status: EmployeeStatus = EmployeeStatus.ACTIVE,
        text_query: str | None = None,
        role: Role | None = None,
        created_from: date | None = None,
        created_to: date | None = None,
    ) -> Page[EmployeeOut]:
        items, total = await repo.search(
            self._session,
            params,
            status=status,
            text_query=text_query,
            roles=frozenset({role}) if role else None,
            created_from=created_from,
            created_to=created_to,
        )
        return Page[EmployeeOut].build([to_out(e) for e in items], total, params)

    async def get(self, employee_id: int) -> EmployeeOut:
        return to_out(await self._get(employee_id))

    async def positions(self, employee_id: int) -> list[PositionOut]:
        await self._get(employee_id)
        return [
            PositionOut(
                role=Role(p.role),
                role_label=ROLE_LABELS[Role(p.role)],
                salary=p.salary,
                valid_from=p.valid_from,
                valid_to=p.valid_to,
            )
            for p in await repo.positions(self._session, employee_id)
        ]

    async def roles_directory(self) -> list[RoleOut]:
        counts = await repo.count_by_role(self._session)
        return [
            RoleOut(role=role, label=ROLE_LABELS[role], employee_count=counts.get(role.value, 0))
            for role in Role
            if role in EMPLOYEE_ROLES and role is not Role.SUPERADMIN  # R-003: yashirin
        ]

    # ------------------------------------------------------------------ yaratish
    async def create(self, data: EmployeeCreate, photo: bytes) -> EmployeeOut:
        if data.role not in EMPLOYEE_ROLES or data.role is Role.SUPERADMIN:
            raise ForbiddenError("Bu lavozimni xodimga berib bo'lmaydi")
        self._require_manage(data.role)
        await self._ensure_phone_free(data.phone)

        photo_path = photos.save_photo(photo)
        employee = Employee(
            first_name=data.first_name,
            last_name=data.last_name,
            birth_date=data.birth_date,
            gender=data.gender.value,
            phone=data.phone,
            role=data.role.value,
            salary=data.salary,
            photo_path=photo_path,
        )
        self._session.add(employee)
        await self._session.flush()
        self._session.add(
            EmployeePosition(
                employee_id=employee.id,
                role=data.role.value,
                salary=data.salary,
                valid_from=today(),
            )
        )
        try:
            await self._session.commit()
        except Exception:
            photos.delete_photo(photo_path)  # baza saqlamasa — fayl ham qolmasin
            raise
        await self._session.refresh(employee)
        return to_out(employee)

    # ------------------------------------------------------------------ tahrirlash
    async def update(self, employee_id: int, data: EmployeeUpdate) -> EmployeeOut:
        employee = await self._get(employee_id)
        self._require_manage(employee.role)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        if "phone" in changes:
            await self._ensure_phone_free(changes["phone"], exclude_id=employee.id)
        for field, value in changes.items():
            setattr(employee, field, getattr(value, "value", value))
        await self._session.commit()
        await self._session.refresh(employee)
        return to_out(employee)

    async def replace_photo(self, employee_id: int, photo: bytes) -> EmployeeOut:
        employee = await self._get(employee_id)
        self._require_manage(employee.role)
        old_path, employee.photo_path = employee.photo_path, photos.save_photo(photo)
        await self._session.commit()
        photos.delete_photo(old_path)
        await self._session.refresh(employee)
        return to_out(employee)

    # ------------------------------------------------------------------ lavozim o'zgarishi
    async def change_position(self, employee_id: int, change: PositionChange) -> EmployeeOut:
        """Kadrlar ko'chirilishi (E-010): eski davr yopiladi, yangisi ochiladi."""
        employee = await self._get(employee_id)
        if employee.archived_at is not None:
            raise EmployeeArchivedError()
        if change.role not in EMPLOYEE_ROLES or change.role is Role.SUPERADMIN:
            raise ForbiddenError("Bu lavozimni xodimga berib bo'lmaydi")
        self._require_manage(employee.role)  # hozirgi lavozimini boshqara oladimi
        self._require_manage(change.role)  # yangi lavozimni bera oladimi

        role_changed = change.role.value != employee.role
        if not role_changed and Decimal(change.salary) == employee.salary:
            raise NothingChangedError()

        current = await repo.open_position(self._session, employee.id)
        if current is not None and change.valid_from < current.valid_from:
            raise InvalidPositionDateError()
        if current is not None and change.valid_from == current.valid_from:
            # O'sha kunning o'zida tuzatish — yangi davr ochilmaydi
            current.role, current.salary = change.role.value, change.salary
        else:
            if current is not None:
                current.valid_to = change.valid_from - timedelta(days=1)
                await self._session.flush()  # "bitta ochiq davr" indeksi buzilmasin
            self._session.add(
                EmployeePosition(
                    employee_id=employee.id,
                    role=change.role.value,
                    salary=change.salary,
                    valid_from=change.valid_from,
                )
            )

        employee.role, employee.salary = change.role.value, change.salary
        if role_changed:
            # Huquqlar o'zgardi → xodim qayta kirishi kerak (A-007)
            await self._logout_everywhere(employee.id, RevokeReason.ROLE_CHANGED)
        await self._session.commit()
        await self._session.refresh(employee)
        return to_out(employee)

    # ------------------------------------------------------------------ arxiv
    async def archive(self, employee_id: int) -> EmployeeOut:
        employee = await self._get(employee_id)
        self._require_manage(employee.role)
        if employee.archived_at is None:
            employee.archived_at = utcnow()
            await self._logout_everywhere(employee.id, RevokeReason.ACCOUNT_DISABLED)
            await self._session.commit()
            await self._session.refresh(employee)
        return to_out(employee)

    async def restore(self, employee_id: int) -> EmployeeOut:
        employee = await self._get(employee_id)
        self._require_manage(employee.role)
        if employee.archived_at is not None:
            await self._ensure_phone_free(employee.phone or "", exclude_id=employee.id)
            employee.archived_at = None
            await self._session.commit()
            await self._session.refresh(employee)
        return to_out(employee)

    # ------------------------------------------------------------------ o'chirish
    async def delete(self, employee_id: int) -> None:
        """Tarixi yo'q — butunlay o'chadi; tarixi bor — shaxsiy ma'lumotlar o'chadi (E-009)."""
        employee = await self._get(employee_id)
        self._require_manage(employee.role)
        old_photo = employee.photo_path

        accounts = await repo.accounts_of(self._session, employee.id)
        if not accounts:  # "tarix" = kamida bir marta login berilgan (keyin kengayadi)
            await repo.delete_completely(self._session, employee)
        else:
            now = utcnow()
            for account in accounts:
                account.deleted_at = account.deleted_at or now
            await self._logout_everywhere(employee.id, RevokeReason.ACCOUNT_DISABLED)
            employee.first_name = "O'chirilgan"
            employee.last_name = f"xodim #{employee.id}"
            employee.phone = None
            employee.photo_path = None
            employee.archived_at = employee.archived_at or now
            employee.anonymized_at = now

        await self._session.commit()
        photos.delete_photo(old_photo)

    # ------------------------------------------------------------------ yordamchi
    async def _logout_everywhere(self, employee_id: int, reason: RevokeReason) -> None:
        now = utcnow()
        for account in await repo.accounts_of(self._session, employee_id):
            account.token_version += 1
            await auth_repo.revoke_active_sessions_of_account(
                self._session, account.id, reason, now
            )
