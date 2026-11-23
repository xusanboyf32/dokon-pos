"""Auth endpoint'lari HTTP darajasida: status kodlar, cookie, xato formati."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.redis import get_redis
from app.core.roles import Role
from tests.integration.test_auth_service import PASSWORD, create_user

LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"


@pytest.fixture
async def api(
    app: FastAPI, db_session: AsyncSession, redis_client: Redis
) -> AsyncIterator[AsyncClient]:
    """Ilova testning tranzaksiyali sessiyasidan foydalanadi — test oxirida hammasi ROLLBACK."""

    async def _test_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _test_session
    app.dependency_overrides[get_redis] = lambda: redis_client
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


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
