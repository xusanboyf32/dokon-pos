"""Telefon raqami: istalgan yozuvdan → bitta formatga (E-011).

Bazada:   +998900021221      (unikallik ishlashi uchun doim bir xil)
Ekranda:  +998 90 002 12 21  (o'qishga qulay)
"""

import re

from app.core.exceptions import AppError

_NON_DIGITS = re.compile(r"\D")


class InvalidPhoneError(AppError):
    code = "INVALID_PHONE"
    message = "Telefon raqami noto'g'ri. Namuna: 90 002 12 21"


def normalize_phone(raw: str) -> str:
    """'90 002-12-21', '+998 (90) 002 12 21', '998900021221' → '+998900021221'."""
    digits = _NON_DIGITS.sub("", raw)
    if len(digits) == 12 and digits.startswith("998"):
        digits = digits[3:]
    if len(digits) != 9:
        raise InvalidPhoneError()
    return f"+998{digits}"


def format_phone(phone: str) -> str:
    """'+998900021221' → '+998 90 002 12 21'."""
    d = phone.removeprefix("+998")
    return f"+998 {d[0:2]} {d[2:5]} {d[5:7]} {d[7:9]}"
