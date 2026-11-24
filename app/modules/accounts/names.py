"""Ekranda ko'rsatish uchun ismlar — audit jurnali va muammolar uchun umumiy.

Har doim bitta so'rov bilan: 50 ta yozuv uchun 50 ta emas, 1 ta so'rov (N+1 yo'q).
Ismlar boshqa jadvallarga nusxalanmaydi — har safar shu yerdan olinadi (E-006).
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts.models import UserAccount
from app.modules.employees.models import Employee


@dataclass(frozen=True, slots=True)
class AccountName:
    username: str
    is_superadmin: bool
    owner_name: str | None  # xodimning ismi (superadmin'da yo'q)

    @property
    def person(self) -> str:
        """Kim: "Ali Valiyev" yoki "Superadmin"."""
        if self.is_superadmin:
            return "Superadmin"
        return self.owner_name or self.username

    @property
    def login_label(self) -> str:
        """Qaysi login: "login «anvar» (Anvar Karimov)" yoki "Superadmin"."""
        if self.is_superadmin:
            return "Superadmin"
        owner = f" ({self.owner_name})" if self.owner_name else ""
        return f"login «{self.username}»{owner}"


def full_name(employee: Employee) -> str:
    return f"{employee.first_name} {employee.last_name}"


async def account_names(session: AsyncSession, ids: set[int]) -> dict[int, AccountName]:
    if not ids:
        return {}
    stmt = (
        select(UserAccount, Employee)
        .outerjoin(Employee, Employee.id == UserAccount.employee_id)
        .where(UserAccount.id.in_(ids))
    )
    return {
        account.id: AccountName(
            username=account.username,
            is_superadmin=account.is_superadmin,
            owner_name=full_name(employee) if employee else None,
        )
        for account, employee in (await session.execute(stmt)).all()
    }


async def employee_names(session: AsyncSession, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    stmt = select(Employee).where(Employee.id.in_(ids))
    return {e.id: full_name(e) for e in (await session.execute(stmt)).scalars()}
