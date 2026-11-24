"""Jurnal yozuvini o'zbekcha gapga aylantirish (summary.py) va cursor."""

from datetime import UTC, datetime

import pytest

from app.core.pagination import InvalidCursorError, decode_cursor, encode_cursor
from app.modules.audit.summary import build_summary, describe_changes, format_money, format_value


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("3500000.00", "3 500 000"),
        ("1250.50", "1 250,50"),
        ("0.00", "0"),
        ("999", "999"),
        ("-15000.00", "-15 000"),
    ],
)
def test_format_money(raw: str, expected: str) -> None:
    assert format_money(raw) == expected


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("role", "kassir", "Kassir"),
        ("phone", "+998900021221", "+998 90 002 12 21"),
        ("birth_date", "2001-05-12", "12.05.2001"),
        ("gender", "female", "ayol"),
        ("permanently_locked", True, "ha"),
        ("first_name", None, "—"),
        ("role", "direktor", "direktor"),  # noma'lum qiymat — xato emas, xom holida
    ],
)
def test_format_value(field: str, value: object, expected: str) -> None:
    assert format_value(field, value) == expected


def test_describe_changes() -> None:
    text = describe_changes(
        {"salary": ["3000000.00", "3500000.00"], "role": ["kassir", "omborchi"]}
    )

    assert text == "Maosh: 3 000 000 → 3 500 000; Lavozim: Kassir → Omborchi"


def test_created_value_has_no_arrow() -> None:
    assert describe_changes({"username": [None, "vali"]}) == "Login: vali"


def test_full_summary() -> None:
    text = build_summary(
        actor_name="Ali Valiyev",
        action_label="Blok ochildi",
        entity_name="login «anvar» (Anvar Karimov)",
        changes={"permanently_locked": [True, False]},
        reason="Parolini unutgan",
    )

    assert text == (
        "Ali Valiyev: blok ochildi — login «anvar» (Anvar Karimov). "
        "Doimiy blok: ha → yo'q. Sabab: Parolini unutgan"
    )


def test_self_action_does_not_repeat_name() -> None:
    text = build_summary(
        actor_name="Anvar Karimov",
        action_label="Tizimga kirdi",
        entity_name="login «anvar» (Anvar Karimov)",
        changes=None,
        reason=None,
        self_action=True,
    )

    assert text == "Anvar Karimov: tizimga kirdi"


def test_cursor_roundtrip() -> None:
    moment = datetime(2026, 11, 24, 10, 30, 15, 123456, tzinfo=UTC)

    assert decode_cursor(encode_cursor(moment, 42)) == (moment, 42)


@pytest.mark.parametrize("bad", ["", "abc", "!!!", encode_cursor.__name__])
def test_broken_cursor_is_rejected(bad: str) -> None:
    with pytest.raises(InvalidCursorError):
        decode_cursor(bad)
