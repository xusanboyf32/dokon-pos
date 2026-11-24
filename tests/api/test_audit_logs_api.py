"""GET /audit-logs: ruxsat, filtrlar, cursor, superadmin yashirinligi, o'zbekcha matn."""

from decimal import Decimal
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import Role
from app.modules.accounts.superadmin import create_superadmin
from app.modules.audit import service as audit
from app.modules.audit.catalog import AuditAction
from tests.integration.test_auth_service import PASSWORD, create_user

AUDIT = "/api/v1/audit-logs"


async def _login(api: AsyncClient, username: str, password: str = PASSWORD) -> None:
    response = await api.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    api.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


async def _as_admin(api: AsyncClient, db_session: AsyncSession) -> int:
    admin = await create_user(
        db_session, username="boshliq", role=Role.ADMIN, phone="+998909999999"
    )
    await _login(api, "boshliq")
    return admin.id


async def _get(api: AsyncClient, **params: Any) -> dict[str, Any]:
    response = await api.get(AUDIT, params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_kassir_cannot_read_audit(api: AsyncClient, db_session: AsyncSession) -> None:
    await create_user(db_session, username="kassir1", role=Role.KASSIR)
    await _login(api, "kassir1")

    assert (await api.get(AUDIT)).status_code == 403


async def test_default_shows_important_and_hides_logins(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    admin_id = await _as_admin(api, db_session)  # login_success — info
    await audit.record(
        db_session,
        actor=audit.ActorRef(admin_id, Role.ADMIN),
        action=AuditAction.EMPLOYEE_SALARY_CHANGED,
        entity=("employee", 1),
        changes={"salary": (Decimal("3000000.00"), Decimal("3500000.00"))},
    )

    default = await _get(api)
    everything = await _get(api, min_severity="info")

    assert [e["action"] for e in default["items"]] == ["employee.salary_changed"]
    assert {e["action"] for e in everything["items"]} == {
        "employee.salary_changed",
        "auth.login_success",
    }
    event = default["items"][0]
    assert event["actor"] == {"account_id": admin_id, "name": "Anvar Karimov", "role": "admin"}
    assert event["entity_name"] == "O'chirilgan xodim #1"  # 1-xodim bazada yo'q
    assert event["summary"] == (
        "Anvar Karimov: maosh o'zgardi — O'chirilgan xodim #1. Maosh: 3 000 000 → 3 500 000"
    )


async def test_filters_are_combined(api: AsyncClient, db_session: AsyncSession) -> None:
    admin_id = await _as_admin(api, db_session)
    kassir = await create_user(db_session, username="kassir1", phone="+998901111111")
    admin = audit.ActorRef(admin_id, Role.ADMIN)
    for action in (AuditAction.EMPLOYEE_ARCHIVED, AuditAction.EMPLOYEE_RESTORED):
        await audit.record(db_session, actor=admin, action=action, entity=("employee", 5))
    await audit.record(
        db_session, actor=admin, action=AuditAction.ACCOUNT_PASSWORD_RESET, entity=("account", 9)
    )
    await audit.record(
        db_session,
        actor=audit.ActorRef(kassir.id, Role.KASSIR),
        action=AuditAction.EMPLOYEE_ARCHIVED,
        entity=("employee", 6),
    )

    async def actions(**params: Any) -> set[str]:
        return {e["action"] for e in (await _get(api, **params))["items"]}

    assert await actions(module="account") == {"account.password_reset"}
    assert await actions(action=["employee.archived", "employee.restored"]) == {
        "employee.archived",
        "employee.restored",
    }
    assert await actions(entity_type="employee", entity_id=6) == {"employee.archived"}
    kassir_items = (await _get(api, actor_employee_id=kassir.employee_id))["items"]
    assert [(e["action"], e["entity_id"]) for e in kassir_items] == [("employee.archived", 6)]
    assert await actions(date_from="2000-01-01", date_to="2000-01-31") == set()


async def test_cursor_pages_through_without_gaps(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    admin_id = await _as_admin(api, db_session)
    for employee_id in range(1, 8):
        await audit.record(
            db_session,
            actor=audit.ActorRef(admin_id, Role.ADMIN),
            action=AuditAction.EMPLOYEE_ARCHIVED,
            entity=("employee", employee_id),
        )

    seen: list[int] = []
    cursor = None
    pages = 0
    while True:
        params: dict[str, Any] = {"limit": 3}
        if cursor:
            params["cursor"] = cursor
        page = await _get(api, **params)
        seen += [e["entity_id"] for e in page["items"]]
        pages += 1
        if not page["has_more"]:
            assert page["next_cursor"] is None
            break
        cursor = page["next_cursor"]

    assert pages == 3
    assert sorted(seen) == list(range(1, 8))  # hech biri tushib qolmadi, takrorlanmadi


async def test_broken_cursor_is_422(api: AsyncClient, db_session: AsyncSession) -> None:
    await _as_admin(api, db_session)

    response = await api.get(AUDIT, params={"cursor": "buzuq"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_CURSOR"


async def test_superadmin_records_are_hidden_from_admin(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    await create_superadmin(db_session, "boss", "parol123", "parol123")
    await _as_admin(api, db_session)

    as_admin = await _get(api, min_severity="info")
    await _login(api, "boss", "parol123")
    as_superadmin = await _get(api, min_severity="info")

    assert "account.superadmin_created" not in {e["action"] for e in as_admin["items"]}
    created = [e for e in as_superadmin["items"] if e["action"] == "account.superadmin_created"]
    assert [e["summary"] for e in created] == ["Tizim: superadmin yaratildi — Superadmin"]
