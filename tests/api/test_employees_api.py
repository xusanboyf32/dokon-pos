"""Xodimlar endpoint'lari HTTP darajasida: multipart forma, ruxsat, xato formati."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.roles import Role
from tests.integration.test_auth_service import PASSWORD, create_user
from tests.integration.test_employee_service import make_photo

EMPLOYEES = "/api/v1/employees"

FORM: dict[str, str] = {
    "first_name": "Anvar",
    "last_name": "Karimov",
    "birth_date": "2001-05-12",
    "gender": "male",
    "phone": "90 111 22 33",
    "role": "kassir",
    "salary": "4000000",
}


async def _auth(api: AsyncClient, db_session: AsyncSession, role: Role = Role.ADMIN) -> None:
    """Foydalanuvchi yaratib, login qilib, tokenni klient sarlavhasiga qo'yadi."""
    await create_user(db_session, username="boshliq", role=role, phone="+998909999999")
    response = await api.post(
        "/api/v1/auth/login", json={"username": "boshliq", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    api.headers["Authorization"] = f"Bearer {response.json()['access_token']}"


async def _create(api: AsyncClient, **overrides: str) -> dict[str, Any]:
    response = await api.post(
        EMPLOYEES,
        data={**FORM, **overrides},
        files={"photo": ("anvar.png", make_photo(), "image/png")},
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_requires_login(api: AsyncClient) -> None:
    response = await api.get(EMPLOYEES)

    assert response.status_code == 401


async def test_kassir_is_forbidden(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session, Role.KASSIR)

    response = await api.get(EMPLOYEES)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_create_and_read_employee(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session)

    created = await _create(api)

    assert created["phone"] == "+998 90 111 22 33"
    assert created["status"] == "active"
    assert created["photo_url"].startswith("/media/employees/")
    card = await api.get(f"{EMPLOYEES}/{created['id']}")
    assert card.status_code == 200
    assert card.json()["full_name"] == "Anvar Karimov"
    photo = await api.get(created["photo_url"])  # rasm ochiq URL orqali beriladi (E-012)
    assert photo.status_code == 200
    assert photo.headers["content-type"] == "image/jpeg"


async def test_photo_is_required(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session)

    response = await api.post(EMPLOYEES, data=FORM)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_bad_phone_is_validation_error(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session)

    response = await api.post(
        EMPLOYEES,
        data={**FORM, "phone": "12345"},
        files={"photo": ("a.png", make_photo(), "image/png")},
    )

    assert response.status_code == 422
    assert "phone" in response.text


async def test_not_an_image_is_rejected(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session)

    response = await api.post(
        EMPLOYEES, data=FORM, files={"photo": ("virus.png", b"MZ\x90\x00", "image/png")}
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PHOTO"


async def test_duplicate_phone_is_conflict(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session)
    await _create(api)

    response = await api.post(
        EMPLOYEES,
        data={**FORM, "phone": "+998901112233"},
        files={"photo": ("a.png", make_photo(), "image/png")},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PHONE_TAKEN"


async def test_list_is_paginated(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session)
    for n in range(3):
        await _create(api, phone=f"90100000{n}")

    response = await api.get(EMPLOYEES, params={"page": 1, "size": 2, "role": "kassir"})

    body = response.json()
    assert response.status_code == 200
    # 3 yangi + _auth yaratgan admin (u kassir emas)
    assert (body["total"], body["pages"], len(body["items"])) == (3, 2, 2)


async def test_page_size_is_limited(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session)

    response = await api.get(EMPLOYEES, params={"size": 1000})

    assert response.status_code == 422


async def test_roles_directory(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session)

    response = await api.get("/api/v1/roles")

    roles = {r["role"] for r in response.json()}
    assert roles == {"admin", "kassir", "omborchi", "buxgalter"}


async def test_position_change_archive_restore_delete_flow(
    api: AsyncClient, db_session: AsyncSession
) -> None:
    await _auth(api, db_session)
    employee = await _create(api)
    url = f"{EMPLOYEES}/{employee['id']}"

    edited = await api.patch(url, json={"last_name": "Valiyev"})
    assert edited.json()["last_name"] == "Valiyev"

    same = await api.post(
        f"{url}/position", json={"role": "kassir", "salary": "4000000", "valid_from": "2099-01-01"}
    )
    assert same.json()["error"]["code"] == "NOTHING_CHANGED"

    history = await api.get(f"{url}/positions")
    assert len(history.json()) == 1

    archived = await api.post(f"{url}/archive")
    assert archived.json()["status"] == "archived"
    restored = await api.post(f"{url}/restore")
    assert restored.json()["status"] == "active"

    deleted = await api.delete(url)
    assert deleted.status_code == 204
    gone = await api.get(url)
    assert gone.status_code == 404
    assert gone.json()["error"]["code"] == "NOT_FOUND"


async def test_replace_photo(api: AsyncClient, db_session: AsyncSession) -> None:
    await _auth(api, db_session)
    employee = await _create(api)

    response = await api.put(
        f"{EMPLOYEES}/{employee['id']}/photo",
        files={"photo": ("new.jpg", make_photo(fmt="JPEG"), "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["photo_url"] != employee["photo_url"]
