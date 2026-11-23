from collections.abc import AsyncIterator

from fastapi import FastAPI
from httpx import AsyncClient

from app.core.database import get_session


async def test_health_returns_ok_and_request_id(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
    assert response.headers["X-Request-ID"]


async def test_request_id_from_client_is_kept(client: AsyncClient) -> None:
    response = await client.get("/health", headers={"X-Request-ID": "kassa-1-abc"})

    assert response.headers["X-Request-ID"] == "kassa-1-abc"


class _BrokenSession:
    async def execute(self, *_: object) -> None:
        raise ConnectionError("baza o'chiq")


async def _broken_session() -> AsyncIterator[_BrokenSession]:
    yield _BrokenSession()


async def test_health_returns_503_when_database_is_down(app: FastAPI, client: AsyncClient) -> None:
    # Haqiqiy bazani o'chirmaymiz — get_session'ni "buzilgan" sessiya bilan almashtiramiz
    app.dependency_overrides[get_session] = _broken_session

    response = await client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "down"}


async def test_unknown_route_returns_404(client: AsyncClient) -> None:
    response = await client.get("/mavjud-emas")

    assert response.status_code == 404
