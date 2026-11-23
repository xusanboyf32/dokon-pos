"""Username va parol qoidalari (A-016, A-017) — bitta joyda.

CLI ham, "Parollar" bo'limi API'si ham shu funksiyalardan foydalanadi.
Baza ham xuddi shu qoidani CHECK bilan kafolatlaydi (ikkinchi himoya qatlami).
"""

import re

from app.core.exceptions import AppError
from app.modules.accounts.models import USERNAME_PATTERN

PASSWORD_MIN_LENGTH = 4
PASSWORD_MAX_LENGTH = 64

_USERNAME_RE = re.compile(USERNAME_PATTERN)


class InvalidUsernameError(AppError):
    code = "INVALID_USERNAME"
    message = "Username 3–50 belgi: lotin harf, raqam, pastki chiziq (_) va nuqta (.)"


class InvalidPasswordError(AppError):
    code = "INVALID_PASSWORD"
    message = f"Parol {PASSWORD_MIN_LENGTH}–{PASSWORD_MAX_LENGTH} belgidan iborat bo'lishi kerak"


class PasswordMismatchError(AppError):
    code = "PASSWORD_MISMATCH"
    message = "Parollar bir xil emas"


def normalize_username(raw: str) -> str:
    """Bo'sh joylar olib tashlanadi, kichik harfga o'tkaziladi, keyin tekshiriladi."""
    username = raw.strip().lower()
    if not _USERNAME_RE.fullmatch(username):
        raise InvalidUsernameError()
    return username


def validate_new_password(password: str, confirmation: str) -> str:
    """Yangi parol: uzunlik + "Takrorlang" maydoni bilan mosligi (A-017)."""
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise InvalidPasswordError()
    if password != confirmation:
        raise PasswordMismatchError()
    return password
