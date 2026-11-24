"""Middleware har so'rov uchun request_id, IP va brauzerni kontekstga yozadi."""

from dataclasses import asdict

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.request_context import current_request


async def test_request_context_is_available_inside_handler(app: FastAPI) -> None:
    @app.get("/_test/context")
    async def show_context() -> dict[str, str | None]:
        return asdict(current_request())

    transport = ASGITransport(app=app, client=("10.0.0.7", 5000))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/_test/context",
            headers={"X-Request-ID": "kassa-1-abc", "User-Agent": "KassaApp/1.0"},
        )

    assert response.json() == {
        "request_id": "kassa-1-abc",
        "ip": "10.0.0.7",
        "user_agent": "KassaApp/1.0",
    }


async def test_long_request_id_is_cut_to_column_size(app: FastAPI) -> None:
    @app.get("/_test/context")
    async def show_context() -> dict[str, str | None]:
        return asdict(current_request())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/_test/context", headers={"X-Request-ID": "a" * 200})

    assert response.json()["request_id"] == "a" * 64
