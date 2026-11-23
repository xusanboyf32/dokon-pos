""" "Parollar" endpoint'lari HTTP darajasida."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import Role
from tests.integration.test_auth_service import PASSWORD, create_user
from tests.integration.test_employees_table import make_employee

ACCOUNTS = "/api/v1/accounts"


async def _auth(api: AsyncClient, db_session: AsyncSession, role: Role = Role.ADMIN) -> None:
    await create_user(db_session, username="boshliq", role=role, phone="+998909999999")
    response = await api.post(
        "/api/v1/auth/login", json={"username": "boshliq", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    api.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


async def test_kassir_is_forbidden(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session, Role.KASSIR)

    response = await api.get(ACCOUNTS)

    assert response.status_code == 403


async def test_full_flow(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session)
    employee = make_employee(phone="+998905555555")
    db_session.add(employee)
    await db_session.flush()

    created = await api.post(
        ACCOUNTS,
        json={
            "employee_id": employee.id,
            "username": "Vali",
            "password": "yangi123",
            "password_confirm": "yangi123",
        },
    )
    assert created.status_code == 201, created.text
    account = created.json()
    assert (account["username"], account["state"]) == ("vali", "active")
    assert "password" not in created.text  # parol ham, hash ham hech qachon qaytmaydi
    url = f"{ACCOUNTS}/{account['id']}"

    duplicate = await api.post(
        ACCOUNTS,
        json={
            "employee_id": employee.id,
            "username": "vali2",
            "password": "yangi123",
            "password_confirm": "yangi123",
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "ACCOUNT_EXISTS"

    mismatch = await api.post(
        f"{url}/reset-password", json={"password": "abcd", "password_confirm": "abce"}
    )
    assert mismatch.json()["error"]["code"] == "PASSWORD_MISMATCH"

    reset = await api.post(
        f"{url}/reset-password", json={"password": "boshqa1", "password_confirm": "boshqa1"}
    )
    assert reset.status_code == 200
    login = await api.post("/api/v1/auth/login", json={"username": "vali", "password": "boshqa1"})
    assert login.status_code == 200

    unlocked = await api.post(f"{url}/unlock")
    assert unlocked.json()["state"] == "active"

    listing = await api.get(ACCOUNTS, params={"search": "vali"})
    assert [a["username"] for a in listing.json()["items"]] == ["vali"]

    assert (await api.delete(url)).status_code == 204
    deleted = await api.get(ACCOUNTS, params={"status": "deleted"})
    assert [a["id"] for a in deleted.json()["items"]] == [account["id"]]


async def test_unknown_account_is_404(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session)

    response = await api.post(f"{ACCOUNTS}/999999/unlock")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
