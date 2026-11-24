"""🔔 Muammolar: blokda o'zi ochiladi, blok ochilganda o'zi yopiladi (N-001…N-009)."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import Role
from app.modules.accounts.superadmin import create_superadmin, unlock_superadmin
from app.modules.auth.service import MAX_FAILED_ATTEMPTS
from app.modules.problems import service as problems
from app.modules.problems.models import Problem
from tests.integration.test_auth_service import PASSWORD, create_user

PROBLEMS = "/api/v1/problems"


async def _login(api: AsyncClient, username: str, password: str = PASSWORD) -> None:
    response = await api.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    api.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


async def _lock(api: AsyncClient, username: str) -> None:
    for _ in range(MAX_FAILED_ATTEMPTS):
        response = await api.post(
            "/api/v1/auth/login", json={"username": username, "password": "xato"}
        )
    assert response.status_code == 423


async def _count(api: AsyncClient) -> int:
    response = await api.get(f"{PROBLEMS}/count")
    assert response.status_code == 200, response.text
    value: int = response.json()["open"]
    return value


async def _list(api: AsyncClient, **params: Any) -> list[dict[str, Any]]:
    response = await api.get(PROBLEMS, params=params)
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def test_lock_opens_problem_and_unlock_closes_it(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    admin = await create_user(
        db_session, username="boshliq", role=Role.ADMIN, phone="+998909999999"
    )
    kassir = await create_user(db_session, username="anvar", phone="+998901111111")
    await _login(api, "boshliq")
    assert await _count(api) == 0

    await _lock(api, "anvar")

    assert await _count(api) == 1
    [problem] = await _list(api)
    assert problem["type"] == "account_locked"
    assert problem["title"] == "login «anvar» (Anvar Karimov) bloklandi"
    assert problem["subject_employee_id"] == kassir.employee_id
    assert problem["action"] == {
        "kind": "unlock_account",
        "label": "Blokni ochish",
        "account_id": kassir.id,
    }

    unlock = await api.post(
        f"/api/v1/accounts/{kassir.id}/unlock", json={"reason": "Parolini unutgan"}
    )
    assert unlock.status_code == 200

    assert await _count(api) == 0
    assert await _list(api) == []  # standart filtr — faqat ochiqlar
    [resolved] = await _list(api, status="resolved")
    assert resolved["resolution"] == "auto"
    assert resolved["resolved_by"] == {"account_id": admin.id, "name": "Anvar Karimov"}
    assert resolved["action"] is None  # yopilgan muammoda tugma yo'q


async def test_new_lock_after_unlock_opens_new_problem(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    """Yopilgan muammo tarixda qoladi; yangi blok — yangi qator (N-003)."""
    await create_user(db_session, username="boshliq", role=Role.ADMIN, phone="+998909999999")
    kassir = await create_user(db_session, username="anvar", phone="+998901111111")
    await _login(api, "boshliq")

    for _ in range(2):
        await _lock(api, "anvar")
        await api.post(f"/api/v1/accounts/{kassir.id}/unlock", json={"reason": "Tekshirildi"})

    assert len(await _list(api, status="all")) == 2
    assert await _count(api) == 0


async def test_repeated_report_is_grouped(db_session: AsyncSession) -> None:
    """N-002: bir xil ochiq muammo — yangi qator emas, hisoblagich."""
    account = await create_user(db_session)

    for _ in range(3):
        await problems.report_account_locked(db_session, account)

    [row] = (await db_session.execute(select(Problem))).scalars().all()
    await db_session.refresh(row)
    assert row.occurrences == 3
    assert row.last_occurred_at >= row.first_occurred_at


async def test_superadmin_problem_is_hidden_from_admin(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    await create_superadmin(db_session, "boss", "parol123", "parol123")
    await create_user(db_session, username="boshliq", role=Role.ADMIN, phone="+998909999999")
    await _lock(api, "boss")

    await _login(api, "boshliq")
    assert await _count(api) == 0

    await unlock_superadmin(db_session)  # CLI — "Tizim"
    [resolved] = (await db_session.execute(select(Problem))).scalars().all()
    await db_session.refresh(resolved)
    assert resolved.status == "resolved"
    assert resolved.resolved_by_account_id is None


async def test_filters(api: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, username="boshliq", role=Role.ADMIN, phone="+998909999999")
    anvar = await create_user(db_session, username="anvar", phone="+998901111111")
    await create_user(db_session, username="vali", phone="+998902222222")
    await _login(api, "boshliq")
    await _lock(api, "anvar")
    await _lock(api, "vali")

    assert len(await _list(api)) == 2
    by_employee = await _list(api, employee_id=anvar.employee_id)
    assert [p["entity_id"] for p in by_employee] == [anvar.id]
    assert len(await _list(api, type="account_locked")) == 2
    assert await _list(api, date_from="2000-01-01", date_to="2000-01-02") == []
    page = (await api.get(PROBLEMS, params={"size": 1})).json()
    assert (page["total"], page["pages"], len(page["items"])) == (2, 2, 1)


async def test_kassir_cannot_see_problems(api: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, username="anvar")
    await _login(api, "anvar")

    assert (await api.get(f"{PROBLEMS}/count")).status_code == 403
    assert (await api.get(PROBLEMS)).status_code == 403
