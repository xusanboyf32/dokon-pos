"""Xodim yoshi: to'liq yillar bo'yicha, 5 dan 100 gacha."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.core.time import to_tashkent, utcnow
from app.modules.employees.schemas import EmployeeUpdate, full_years


def _years_ago(years: int) -> date:
    today = to_tashkent(utcnow()).date()
    if (today.month, today.day) == (2, 29):  # kabisa yili chekkasi
        today -= timedelta(days=1)
    return today.replace(year=today.year - years)


@pytest.mark.parametrize(
    ("birth", "on", "years"),
    [
        (date(2001, 5, 12), date(2026, 5, 11), 24),  # tug'ilgan kun ertaga
        (date(2001, 5, 12), date(2026, 5, 12), 25),  # bugun
        (date(2000, 2, 29), date(2026, 2, 28), 25),
        (date(2000, 2, 29), date(2026, 3, 1), 26),
    ],
)
def test_full_years(birth: date, on: date, years: int) -> None:
    assert full_years(birth, on) == years


@pytest.mark.parametrize(
    "birth",
    [_years_ago(5), _years_ago(30), _years_ago(100) + timedelta(days=1)],
)
def test_allowed_ages(birth: date) -> None:
    assert EmployeeUpdate(birth_date=birth).birth_date == birth


@pytest.mark.parametrize(
    "birth",
    [
        _years_ago(5) + timedelta(days=1),  # 5 yoshga ertaga to'ladi → hozir 4
        _years_ago(101),
        to_tashkent(utcnow()).date(),
        to_tashkent(utcnow()).date() + timedelta(days=1),
    ],
)
def test_rejected_ages(birth: date) -> None:
    with pytest.raises(ValidationError, match="5 dan 100 gacha"):
        EmployeeUpdate(birth_date=birth)
