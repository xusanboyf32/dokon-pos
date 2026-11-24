"""Pul doim 2 xonali Decimal bo'lib keladi (D-005)."""

from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from app.core.money import Money

money = TypeAdapter(Money)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("4500000", "4500000.00"), ("4500000.5", "4500000.50"), (0, "0.00"), ("12.34", "12.34")],
)
def test_money_always_has_two_decimals(raw: object, expected: str) -> None:
    value = money.validate_python(raw)

    assert isinstance(value, Decimal)
    assert str(value) == expected


@pytest.mark.parametrize("raw", ["-1", "0.001", "1e20"])
def test_invalid_money_is_rejected(raw: str) -> None:
    with pytest.raises(ValidationError):
        money.validate_python(raw)
