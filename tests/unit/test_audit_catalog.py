"""Audit katalogi va `changes` tayyorlash qoidalari (AU-002, AU-008)."""

import re
from datetime import date
from decimal import Decimal

import pytest

from app.core.roles import Role
from app.modules.audit.catalog import CATALOG, AuditAction
from app.modules.audit.models import ACTION_PATTERN
from app.modules.audit.service import build_changes


def test_every_action_has_spec() -> None:
    assert set(CATALOG) == set(AuditAction)


@pytest.mark.parametrize("action", list(AuditAction))
def test_action_name_matches_db_format(action: AuditAction) -> None:
    assert re.fullmatch(ACTION_PATTERN, action.value)


@pytest.mark.parametrize("action", list(AuditAction))
def test_no_generic_updated_actions(action: AuditAction) -> None:
    # AU-008: "employee.updated" dan nima o'zgargani tushunarsiz
    assert not action.value.endswith((".updated", ".changed"))


def test_unlock_requires_reason() -> None:
    assert CATALOG[AuditAction.ACCOUNT_UNLOCKED].reason_required


def test_unchanged_fields_are_dropped() -> None:
    changes = build_changes({"first_name": ("Anvar", "Anvar"), "last_name": ("Karimov", "Valiyev")})

    assert changes == {"last_name": ["Karimov", "Valiyev"]}


def test_nothing_changed_gives_none() -> None:
    assert build_changes({"first_name": ("Anvar", "Anvar")}) is None
    assert build_changes(None) is None
    assert build_changes({}) is None


def test_money_is_stored_as_exact_string() -> None:
    changes = build_changes({"salary": (Decimal("3000000.00"), Decimal("3500000.50"))})

    assert changes == {"salary": ["3000000.00", "3500000.50"]}


def test_float_is_rejected() -> None:
    with pytest.raises(TypeError):
        build_changes({"salary": (Decimal("1.00"), 1.5)})


def test_enum_and_date_are_converted() -> None:
    changes = build_changes(
        {"role": (Role.KASSIR, Role.OMBORCHI), "birth_date": (None, date(2000, 1, 31))}
    )

    assert changes == {"role": ["kassir", "omborchi"], "birth_date": [None, "2000-01-31"]}


def test_created_object_uses_none_as_old_value() -> None:
    changes = build_changes({"first_name": (None, "Anvar")})

    assert changes == {"first_name": [None, "Anvar"]}


@pytest.mark.parametrize("field", ["password", "password_hash", "refresh_token", "Secret_Key"])
def test_secret_fields_are_never_written(field: str) -> None:
    with pytest.raises(ValueError, match="Maxfiy"):
        build_changes({field: ("old", "new")})
