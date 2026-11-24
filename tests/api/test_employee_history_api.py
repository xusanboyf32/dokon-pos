"""GET /employees/{id}/history — xodim kartochkasidagi "Tarix" tabi (AU-019)."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import Role
from tests.api.test_employees_api import EMPLOYEES, _auth, _create
from tests.integration.test_auth_service import PASSWORD, create_user

ACCOUNTS = "/api/v1/accounts"


async def _history(api: AsyncClient, employee_id: int, **params: Any) -> list[str]:
    response = await api.get(f"{EMPLOYEES}/{employee_id}/history", params=params)
    assert response.status_code == 200, response.text
    return [e["action"] for e in response.json()["items"]]


async def test_history_joins_employee_and_account_events(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    await _auth(api, db_session)
    anvar = await _create(api)
    other = await _create(api, phone="90 222 33 44", first_name="Vali")
    created = await api.post(
        ACCOUNTS,
        json={
            "employee_id": anvar["id"],
            "username": "anvar",
            "password": "parol12",
            "password_confirm": "parol12",
        },
    )
    await api.post(f"{ACCOUNTS}/{created.json()['id']}/unlock", json={"reason": "Tekshiruv"})
    await api.post(
        f"{EMPLOYEES}/{anvar['id']}/position",
        json={"role": "kassir", "salary": "4500000", "valid_from": "2099-01-01"},
    )
    await api.post(f"{EMPLOYEES}/{other['id']}/archive")  # boshqa xodim — aralashmasin

    history = await _history(api, anvar["id"])

    # Eng yangisi tepada; xodim va login yozuvlari bitta ro'yxatda, muhimlikdan qat'i nazar
    assert history == [
        "employee.salary_changed",
        "account.unlocked",
        "account.created",
        "employee.created",
    ]


async def test_logins_are_hidden_by_default(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session)
    kassir = await create_user(db_session, username="kassir1", phone="+998901111111")
    login = await api.post("/api/v1/auth/login", json={"username": "kassir1", "password": PASSWORD})
    assert login.status_code == 200
    assert kassir.employee_id is not None

    assert await _history(api, kassir.employee_id) == []
    assert await _history(api, kassir.employee_id, include_logins=True) == ["auth.login_success"]


async def test_history_is_paginated(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session)
    employee = await _create(api)
    url = f"{EMPLOYEES}/{employee['id']}"
    for _ in range(2):
        await api.post(f"{url}/archive")
        await api.post(f"{url}/restore")

    first = (await api.get(f"{url}/history", params={"limit": 3})).json()
    second = (
        await api.get(f"{url}/history", params={"limit": 3, "cursor": first["next_cursor"]})
    ).json()

    assert first["has_more"] is True
    assert len(first["items"]) == 3
    assert second["has_more"] is False
    assert len(second["items"]) == 2  # 1 ta yaratish + 4 ta arxiv/qaytarish = 5


async def test_unknown_or_deleted_employee_is_404(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    await _auth(api, db_session)
    employee = await _create(api)
    await api.delete(f"{EMPLOYEES}/{employee['id']}")

    for employee_id in (employee["id"], 999999):
        response = await api.get(f"{EMPLOYEES}/{employee_id}/history")
        assert response.status_code == 404


async def test_kassir_cannot_see_history(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session, Role.KASSIR)

    assert (await api.get(f"{EMPLOYEES}/1/history")).status_code == 403
