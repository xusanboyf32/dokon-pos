"""Rollar va darajalar (DECISIONS: R-001, R-005, R-006).

Rollar qat'iy — 6 ta, yangi rol qo'shilmaydi.
"Kim kimni boshqara oladi" qoidasi shu yerda, bitta joyda.
"""

from enum import StrEnum


class Role(StrEnum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    KASSIR = "kassir"
    OMBORCHI = "omborchi"
    BUXGALTER = "buxgalter"
    TAMINOTCHI = "taminotchi"


ROLE_LABELS: dict[Role, str] = {
    Role.SUPERADMIN: "Superadmin",
    Role.ADMIN: "Admin",
    Role.KASSIR: "Kassir",
    Role.OMBORCHI: "Omborchi",
    Role.BUXGALTER: "Buxgalter",
    Role.TAMINOTCHI: "Ta'minotchi",
}

# 1 — eng yuqori daraja. Past daraja = katta raqam.
ROLE_LEVEL: dict[Role, int] = {
    Role.SUPERADMIN: 1,
    Role.ADMIN: 2,
    Role.KASSIR: 3,
    Role.OMBORCHI: 3,
    Role.BUXGALTER: 3,
    Role.TAMINOTCHI: 3,
}

# Xodimga beriladigan lavozimlar. Ta'minotchi xodim emas — u alohida ob'ekt.
EMPLOYEE_ROLES: frozenset[Role] = frozenset(Role) - {Role.TAMINOTCHI}


def can_manage(actor: Role, target: Role) -> bool:
    """Foydalanuvchi faqat o'zidan PAST darajali rolni boshqaradi.

    superadmin → hammani (admin'ni ham); admin → faqat 3-daraja; qolganlar → hech kimni.
    """
    if ROLE_LEVEL[actor] >= 3:
        return False
    return ROLE_LEVEL[actor] < ROLE_LEVEL[target]
