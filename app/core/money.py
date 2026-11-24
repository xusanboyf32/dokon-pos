"""Pul (D-005): faqat `Decimal`, doim 2 xona (tiyin), UZS.

API'ga kelgan "4500000" ham, "4500000.5" ham darhol "4500000.00" / "4500000.50" ko'rinishiga
keltiriladi. Shunda bazadagi, javobdagi va audit jurnalidagi qiymat bir xil yoziladi.
"""

from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, Field

TIYIN = Decimal("0.01")


def to_money(value: Decimal) -> Decimal:
    return value.quantize(TIYIN)


# Manfiy bo'lmagan summa: maosh, narx, to'lov
Money = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2), AfterValidator(to_money)]
