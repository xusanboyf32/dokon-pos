"""Jurnal yozuvini odam o'qiydigan o'zbekcha gapga aylantirish.

Sof funksiyalar: bazaga murojaat yo'q, faqat tayyor ma'lumotdan matn yasaydi.

    "Ali Valiyev: maosh o'zgardi — Anvar Karimov. Maosh: 3 000 000 → 3 500 000"
    "Tizim: hisob vaqtincha bloklandi — login «anvar» (Anvar Karimov)"
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.core.roles import ROLE_LABELS, Role
from app.modules.employees.phone import format_phone

SYSTEM_NAME = "Tizim"

FIELD_LABELS: dict[str, str] = {
    "first_name": "Ism",
    "last_name": "Familiya",
    "birth_date": "Tug'ilgan sana",
    "gender": "Jins",
    "phone": "Telefon",
    "role": "Lavozim",
    "salary": "Maosh",
    "username": "Login",
    "employee_id": "Xodim",
    "permanently_locked": "Doimiy blok",
}

_GENDER_LABELS = {"male": "erkak", "female": "ayol"}
_MONEY_FIELDS = {"salary"}


def format_money(raw: str) -> str:
    """'3500000.00' → '3 500 000'; tiyin bo'lsa saqlanadi: '1250.50' → '1 250,50'."""
    amount = Decimal(raw)
    whole, cents = divmod(abs(amount), 1)
    text = f"{int(whole):,}".replace(",", " ")
    if cents:
        text += f",{int(cents * 100):02d}"
    return f"-{text}" if amount < 0 else text


def format_value(field: str, value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "ha" if value else "yo'q"
    try:
        if field in _MONEY_FIELDS:
            return format_money(str(value))
        if field == "role":
            return ROLE_LABELS[Role(value)]
        if field == "phone":
            return format_phone(str(value))
        if field == "birth_date":
            return date.fromisoformat(str(value)).strftime("%d.%m.%Y")
    except (ValueError, KeyError, InvalidOperation):
        return str(value)  # kutilmagan qiymat — xom holida, lekin xato bermaydi
    if field == "gender":
        return _GENDER_LABELS.get(str(value), str(value))
    return str(value)


def describe_changes(changes: dict[str, Any] | None) -> str:
    """{"salary": ["3000000.00", "3500000.00"]} → "Maosh: 3 000 000 → 3 500 000"."""
    if not changes:
        return ""
    parts = []
    for field, pair in changes.items():
        old, new = pair if isinstance(pair, list) and len(pair) == 2 else (None, pair)
        label = FIELD_LABELS.get(field, field)
        if old is None:  # yangi yaratilgan — faqat qiymat
            parts.append(f"{label}: {format_value(field, new)}")
        else:
            parts.append(f"{label}: {format_value(field, old)} → {format_value(field, new)}")
    return "; ".join(parts)


def build_summary(
    *,
    actor_name: str,
    action_label: str,
    entity_name: str,
    changes: dict[str, Any] | None,
    reason: str | None,
    self_action: bool = False,
) -> str:
    """`self_action` — aktyor o'z ustida amal qilgan (tizimga kirdi): nom takrorlanmaydi."""
    text = f"{actor_name}: {action_label[0].lower()}{action_label[1:]}"
    if not self_action:
        text += f" — {entity_name}"
    details = describe_changes(changes)
    if details:
        text += f". {details}"
    if reason:
        text += f". Sabab: {reason}"
    return text
