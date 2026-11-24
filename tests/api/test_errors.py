"""Xato formati hamma joyda bir xil ekanini tekshiradi (docs/API_CONVENTIONS.md, 3-bo'lim)."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import BaseModel

from app.core.exceptions import ConflictError, NotFoundError
from app.main import create_app


class _PriceIn(BaseModel):
    price: int


@pytest.fixture
def app() -> FastAPI:
    """Umumiy `app` fixture'ini almashtiradi: xato ko'taradigan sinov endpoint'lari qo'shiladi."""
    test_app = create_app()

    @test_app.get("/_test/conflict")
    async def conflict() -> None:
        raise ConflictError("Bu nom band", code="NAME_TAKEN", details={"name": "cola"})

    @test_app.get("/_test/not-found")
    async def not_found() -> None:
        raise NotFoundError()

    @test_app.get("/_test/crash")
    async def crash() -> None:
        raise RuntimeError("maxfiy ichki tafsilot")

    @test_app.post("/_test/validate")
    async def validate(body: _PriceIn) -> _PriceIn:
        return body

    return test_app


async def test_app_error_has_unified_format(client: AsyncClient) -> None:
    response = await client.get("/_test/conflict", headers={"X-Request-ID": "req-1"})

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "NAME_TAKEN",
            "message": "Bu nom band",
            "details": {"name": "cola"},
            "request_id": "req-1",
        }
    }


async def test_app_error_uses_class_defaults(client: AsyncClient) -> None:
    response = await client.get("/_test/not-found")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["message"] == "Topilmadi"


async def test_validation_error_lists_fields(client: AsyncClient) -> None:
    response = await client.post("/_test/validate", json={"price": "ko'p"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["fields"][0]["field"] == "price"


async def test_unhandled_error_hides_internal_details(client: AsyncClient) -> None:
    response = await client.get("/_test/crash")

    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    # Ichki xato matni foydalanuvchiga ko'rinmasligi shart
    assert "maxfiy" not in response.text


async def test_broken_json_gets_clear_uzbek_message(api: AsyncClient) -> None:
    response = await api.post(
        "/api/v1/auth/login",
        content='{"username": "anvar", "password": ',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_JSON"
    assert error["message"].startswith("So'rov matni noto'g'ri yozilgan (JSON)")
    assert isinstance(error["details"]["position"], int)


async def test_missing_field_message_is_uzbek(api: AsyncClient) -> None:
    response = await api.post("/api/v1/auth/login", json={"username": "anvar"})

    fields = response.json()["error"]["details"]["fields"]
    assert {"field": "password", "message": "Bu maydon majburiy"} in fields
