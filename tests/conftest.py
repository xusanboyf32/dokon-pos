"""Barcha testlar uchun umumiy fixture'lar.

- `app`    — har test uchun yangi FastAPI ilovasi (testlar bir-biriga ta'sir qilmaydi)
- `client` — shu ilovaga so'rov yuboradigan HTTP klient (server ishga tushirilmaydi)
"""

import os

# Ilova import qilinishidan OLDIN test muhitini belgilaymiz:
# muhit o'zgaruvchisi .env dagi qiymatdan ustun turadi (pydantic-settings qoidasi).
os.environ["ENVIRONMENT"] = "test"

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture
def app() -> FastAPI:
    return create_app()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    # raise_app_exceptions=False: kutilmagan xatoda test yiqilmaydi,
    # balki ilova foydalanuvchiga nima qaytarishini (500) tekshiramiz
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client
