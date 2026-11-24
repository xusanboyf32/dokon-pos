"""Auth endpoint'lari HTTP darajasida: status kodlar, cookie, xato formati."""

from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import Role
from app.modules.employees.models import EmployeePosition
from tests.integration.test_auth_service import PASSWORD, create_user

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"


async def _login(api: AsyncClient, username: str = "anvar") -> str:
    response = await api.post(LOGIN, json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


async def test_login_returns_token_and_sets_secure_cookie(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session)

    response = await api.post(LOGIN, json={"username": "anvar", "password": PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["role"] == "kassir"
    assert "refresh_token" not in body  # refresh faqat cookie'da
    cookie = response.headers["set-cookie"].lower()
    assert "refresh_token=" in cookie
    assert "httponly" in cookie
    assert "samesite=strict" in cookie
    assert "path=/api/v1/auth" in cookie


async def test_wrong_password_returns_401_in_unified_format(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session)

    response = await api.post(LOGIN, json={"username": "anvar", "password": "9999"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert response.json()["error"]["message"] == "Login yoki parol xato"


async def test_empty_login_body_returns_422(api: AsyncClient) -> None:
    response = await api.post(LOGIN, json={"username": "", "password": ""})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_me_with_token(api: AsyncClient, db_session: AsyncSession) -> None:
    account = await create_user(db_session, role=Role.BUXGALTER)
    token = await _login(api)

    response = await api.get(ME, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "account_id": account.id,
        "role": "buxgalter",
        "employee_id": account.employee_id,
    }


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer yaroqsiz"}, {"Authorization": "Basic abc"}],
)
async def test_me_without_valid_token_returns_401(
    api: AsyncClient, headers: dict[str, str]
) -> None:
    response = await api.get(ME, headers=headers)

    assert response.status_code == 401
    assert "error" in response.json()


async def test_refresh_uses_cookie_and_rotates_it(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session)
    await _login(api)
    old_cookie = api.cookies.get("refresh_token", path="/api/v1/auth")

    response = await api.post(REFRESH)

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert api.cookies.get("refresh_token", path="/api/v1/auth") != old_cookie


async def test_refresh_without_cookie_returns_401(api: AsyncClient) -> None:
    response = await api.post(REFRESH)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "SESSION_INVALID"


async def test_logout_then_token_and_cookie_stop_working(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session)
    token = await _login(api)
    auth = {"Authorization": f"Bearer {token}"}
    refresh_cookie = api.cookies.get("refresh_token", path="/api/v1/auth")

    logout = await api.post(LOGOUT, headers=auth)

    assert logout.status_code == 204
    assert (await api.get(ME, headers=auth)).status_code == 401
    # Server cookie'ni o'chirdi — lekin o'g'ri eski qiymatni saqlab qolgan bo'lsa-chi?
    api.cookies.set("refresh_token", str(refresh_cookie), path="/api/v1/auth")
    stale = await api.post(REFRESH)
    assert stale.status_code == 401


async def test_employee_sees_only_own_position_history(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    """AU-020: "Mening sahifam" — faqat o'z lavozim/maosh davrlari."""
    me = await create_user(db_session, username="anvar")
    other = await create_user(db_session, username="vali", phone="+998902222222")
    assert me.employee_id is not None and other.employee_id is not None
    db_session.add_all(
        [
            EmployeePosition(
                employee_id=me.employee_id,
                role="kassir",
                salary=Decimal("3000000.00"),
                valid_from=date(2026, 3, 1),
                valid_to=date(2026, 8, 31),
            ),
            EmployeePosition(
                employee_id=me.employee_id,
                role="kassir",
                salary=Decimal("3500000.00"),
                valid_from=date(2026, 9, 1),
            ),
            EmployeePosition(
                employee_id=other.employee_id,
                role="kassir",
                salary=Decimal("9000000.00"),
                valid_from=date(2026, 1, 1),
            ),
        ]
    )
    await db_session.flush()
    login = await api.post("/api/v1/auth/login", json={"username": "anvar", "password": PASSWORD})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await api.get("/api/v1/auth/me/positions", headers=headers)

    assert response.status_code == 200
    assert [(p["salary"], p["valid_to"]) for p in response.json()] == [
        ("3500000.00", None),
        ("3000000.00", "2026-08-31"),
    ]


async def test_my_positions_requires_login(api: AsyncClient) -> None:
    assert (await api.get("/api/v1/auth/me/positions")).status_code == 401
