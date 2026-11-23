"""Telefon raqami: normallashtirish va chiroyli ko'rinish (E-011)."""

import pytest

from app.modules.employees.phone import InvalidPhoneError, format_phone, normalize_phone


@pytest.mark.parametrize(
    "raw",
    [
        "900021221",
        "90 002 12 21",
        "90-002-12-21",
        "(90) 002-12-21",
        "998900021221",
        "+998900021221",
        "+998 (90) 002 12 21",
        "  +998 90 002 12 21  ",
    ],
)
def test_any_spelling_becomes_one_format(raw: str) -> None:
    assert normalize_phone(raw) == "+998900021221"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "90002122",  # 8 raqam
        "9000212211",  # 10 raqam
        "997900021221",  # boshqa davlat kodi
        "+7 900 002 12 21",
        "telefon yo'q",
    ],
)
def test_invalid_numbers_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidPhoneError):
        normalize_phone(raw)


def test_format_for_screen() -> None:
    assert format_phone("+998900021221") == "+998 90 002 12 21"
