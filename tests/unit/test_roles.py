import pytest

from app.core.roles import EMPLOYEE_ROLES, Role, can_manage

LOW_ROLES = [Role.KASSIR, Role.OMBORCHI, Role.BUXGALTER, Role.TAMINOTCHI]


@pytest.mark.parametrize("target", [Role.ADMIN, *LOW_ROLES])
def test_superadmin_manages_everyone_below(target: Role) -> None:
    assert can_manage(Role.SUPERADMIN, target)


@pytest.mark.parametrize("target", LOW_ROLES)
def test_admin_manages_low_roles(target: Role) -> None:
    assert can_manage(Role.ADMIN, target)


@pytest.mark.parametrize("target", [Role.SUPERADMIN, Role.ADMIN])
def test_admin_cannot_manage_admin_or_superadmin(target: Role) -> None:
    assert not can_manage(Role.ADMIN, target)


def test_superadmin_cannot_manage_superadmin() -> None:
    assert not can_manage(Role.SUPERADMIN, Role.SUPERADMIN)


@pytest.mark.parametrize("actor", LOW_ROLES)
@pytest.mark.parametrize("target", list(Role))
def test_low_roles_manage_nobody(actor: Role, target: Role) -> None:
    assert not can_manage(actor, target)


def test_taminotchi_is_not_an_employee_role() -> None:
    assert Role.TAMINOTCHI not in EMPLOYEE_ROLES
    assert len(EMPLOYEE_ROLES) == 5
