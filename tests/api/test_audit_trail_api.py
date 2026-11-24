"""Parollar va Xodimlar endpoint'lari jurnalga to'g'ri yozilishi (AU-002, AU-006, AU-012)."""

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.catalog import AuditAction
from app.modules.audit.models import AuditEvent
from tests.api.test_employees_api import EMPLOYEES, _auth, _create
from tests.integration.test_employee_service import make_photo

ACCOUNTS = "/api/v1/accounts"


async def events(session: AsyncSession, entity_type: str, entity_id: int) -> list[AuditEvent]:
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
        .order_by(AuditEvent.id)
    )
    return list((await session.execute(stmt)).scalars())


async def test_account_actions_are_recorded_without_password(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    await _auth(api, db_session)
    employee = await _create(api)
    new_password = {"password": "yangi123", "password_confirm": "yangi123"}

    created = await api.post(
        ACCOUNTS, json={"employee_id": employee["id"], "username": "vali", **new_password}
    )
    url = f"{ACCOUNTS}/{created.json()['id']}"
    await api.post(f"{url}/reset-password", json=new_password)
    await api.post(f"{url}/unlock", json={"reason": "  Parolini unutgan  "})
    await api.delete(url)

    trail = await events(db_session, "account", created.json()["id"])
    assert [e.action for e in trail] == [
        AuditAction.ACCOUNT_CREATED,
        AuditAction.ACCOUNT_PASSWORD_RESET,
        AuditAction.ACCOUNT_UNLOCKED,
        AuditAction.ACCOUNT_DELETED,
    ]
    assert trail[0].changes == {"username": [None, "vali"], "employee_id": [None, employee["id"]]}
    assert trail[2].reason == "Parolini unutgan"
    assert all(e.actor_role == "admin" and e.request_id for e in trail)
    # Parol ham, hash ham jurnalning hech qayerida yo'q (AU-002)
    assert not any("yangi123" in str(e.changes) or "argon2" in str(e.changes) for e in trail)


async def test_unlock_without_reason_is_rejected(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    await _auth(api, db_session)
    employee = await _create(api)
    created = await api.post(
        ACCOUNTS,
        json={
            "employee_id": employee["id"],
            "username": "vali",
            "password": "yangi123",
            "password_confirm": "yangi123",
        },
    )
    url = f"{ACCOUNTS}/{created.json()['id']}/unlock"

    for body in (None, {"reason": ""}, {"reason": "   "}):
        response = await api.post(url, json=body)
        assert response.status_code == 422, body

    assert [e.action for e in await events(db_session, "account", created.json()["id"])] == [
        AuditAction.ACCOUNT_CREATED  # blok ochilmadi — yozuv ham yo'q
    ]


async def test_employee_lifecycle_is_recorded_with_values(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    await _auth(api, db_session)
    employee = await _create(api)
    url = f"{EMPLOYEES}/{employee['id']}"

    await api.patch(url, json={"last_name": "Valiyev", "first_name": "Anvar"})  # ism o'zgarmadi
    await api.patch(url, json={"last_name": "Valiyev"})  # hech narsa o'zgarmadi — yozuv yo'q
    await api.put(f"{url}/photo", files={"photo": ("a.jpg", make_photo(fmt="JPEG"), "image/jpeg")})
    await api.post(
        f"{url}/position", json={"role": "kassir", "salary": "4500000", "valid_from": "2099-01-01"}
    )
    await api.post(
        f"{url}/position",
        json={"role": "omborchi", "salary": "5000000", "valid_from": "2099-02-01"},
    )
    await api.post(f"{url}/archive")
    await api.post(f"{url}/archive")  # takroriy — yozuv yo'q
    await api.post(f"{url}/restore")
    await api.delete(url)

    trail = await events(db_session, "employee", employee["id"])
    assert [e.action for e in trail] == [
        AuditAction.EMPLOYEE_CREATED,
        AuditAction.EMPLOYEE_PERSONAL_INFO_CHANGED,
        AuditAction.EMPLOYEE_PHOTO_CHANGED,
        AuditAction.EMPLOYEE_SALARY_CHANGED,
        AuditAction.EMPLOYEE_ROLE_CHANGED,
        AuditAction.EMPLOYEE_ARCHIVED,
        AuditAction.EMPLOYEE_RESTORED,
        AuditAction.EMPLOYEE_DELETED,
    ]
    created, personal, _, salary, role, _, _, deleted = trail
    assert created.changes is not None
    assert created.changes["phone"] == [None, "+998901112233"]  # qaror AU-013: to'liq qiymat
    assert personal.changes == {"last_name": ["Karimov", "Valiyev"]}
    assert salary.changes == {"salary": ["4000000.00", "4500000.00"]}
    assert role.changes == {
        "role": ["kassir", "omborchi"],
        "salary": ["4500000.00", "5000000.00"],  # bitta yozuv ichida (AU-011)
    }
    assert deleted.changes == {
        "first_name": ["Anvar", None],
        "last_name": ["Valiyev", None],
        "phone": ["+998901112233", None],
    }
