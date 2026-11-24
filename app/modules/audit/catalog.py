"""Audit amallari katalogi (DECISIONS: AU-005, AU-006, AU-008).

Jurnalga faqat shu ro'yxatdagi amallar yoziladi. Har amalda:
  - nom: `modul.amal` (masalan `employee.salary_changed`); umumiy `*.updated` taqiqlangan
  - muhimlik: info / important / critical — chaqiruvchi emas, katalog belgilaydi
  - sabab majburiymi
  - o'zbekcha qisqa nom (jurnal ro'yxati va filtr uchun)

Yangi amal kerak bo'lsa — shu yerga qo'shiladi. Migratsiya kerak emas (bazada faqat format CHECK).
"""

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    INFO = "info"
    IMPORTANT = "important"
    CRITICAL = "critical"


class AuditAction(StrEnum):
    # auth — kirish va bloklar (AU-004: har bir xato urinish yozilmaydi)
    AUTH_LOGIN_SUCCESS = "auth.login_success"
    AUTH_LOCKED_TEMPORARY = "auth.locked_temporary"
    AUTH_LOCKED_PERMANENT = "auth.locked_permanent"
    AUTH_TOKEN_REUSE_DETECTED = "auth.token_reuse_detected"

    # account — "Parollar" bo'limi
    ACCOUNT_CREATED = "account.created"
    ACCOUNT_PASSWORD_RESET = "account.password_reset"
    ACCOUNT_UNLOCKED = "account.unlocked"
    ACCOUNT_DELETED = "account.deleted"
    ACCOUNT_SUPERADMIN_CREATED = "account.superadmin_created"
    ACCOUNT_SUPERADMIN_UNLOCKED = "account.superadmin_unlocked"

    # employee — "Xodimlar" bo'limi
    EMPLOYEE_CREATED = "employee.created"
    EMPLOYEE_PERSONAL_INFO_CHANGED = "employee.personal_info_changed"
    EMPLOYEE_PHOTO_CHANGED = "employee.photo_changed"
    EMPLOYEE_ROLE_CHANGED = "employee.role_changed"
    EMPLOYEE_SALARY_CHANGED = "employee.salary_changed"
    EMPLOYEE_ARCHIVED = "employee.archived"
    EMPLOYEE_RESTORED = "employee.restored"
    EMPLOYEE_DELETED = "employee.deleted"


@dataclass(frozen=True, slots=True)
class ActionSpec:
    severity: Severity
    label: str
    reason_required: bool = False


_I, _M, _C = Severity.INFO, Severity.IMPORTANT, Severity.CRITICAL

CATALOG: dict[AuditAction, ActionSpec] = {
    AuditAction.AUTH_LOGIN_SUCCESS: ActionSpec(_I, "Tizimga kirdi"),
    AuditAction.AUTH_LOCKED_TEMPORARY: ActionSpec(_M, "Hisob vaqtincha bloklandi"),
    AuditAction.AUTH_LOCKED_PERMANENT: ActionSpec(_C, "Hisob doimiy bloklandi"),
    AuditAction.AUTH_TOKEN_REUSE_DETECTED: ActionSpec(_C, "Token qayta ishlatildi (o'g'irlik)"),
    AuditAction.ACCOUNT_CREATED: ActionSpec(_M, "Login yaratildi"),
    AuditAction.ACCOUNT_PASSWORD_RESET: ActionSpec(_M, "Parol almashtirildi"),
    AuditAction.ACCOUNT_UNLOCKED: ActionSpec(_C, "Blok ochildi", reason_required=True),
    AuditAction.ACCOUNT_DELETED: ActionSpec(_M, "Login o'chirildi"),
    AuditAction.ACCOUNT_SUPERADMIN_CREATED: ActionSpec(_C, "Superadmin yaratildi"),
    AuditAction.ACCOUNT_SUPERADMIN_UNLOCKED: ActionSpec(_C, "Superadmin bloki ochildi"),
    AuditAction.EMPLOYEE_CREATED: ActionSpec(_I, "Xodim qo'shildi"),
    AuditAction.EMPLOYEE_PERSONAL_INFO_CHANGED: ActionSpec(_I, "Shaxsiy ma'lumotlar o'zgardi"),
    AuditAction.EMPLOYEE_PHOTO_CHANGED: ActionSpec(_I, "Rasm almashtirildi"),
    AuditAction.EMPLOYEE_ROLE_CHANGED: ActionSpec(_M, "Lavozim o'zgardi"),
    AuditAction.EMPLOYEE_SALARY_CHANGED: ActionSpec(_M, "Maosh o'zgardi"),
    AuditAction.EMPLOYEE_ARCHIVED: ActionSpec(_M, "Xodim arxivlandi"),
    AuditAction.EMPLOYEE_RESTORED: ActionSpec(_M, "Xodim arxivdan qaytarildi"),
    AuditAction.EMPLOYEE_DELETED: ActionSpec(_C, "Xodim o'chirildi"),
}


def spec_of(action: AuditAction) -> ActionSpec:
    return CATALOG[action]
