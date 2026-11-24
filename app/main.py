"""FastAPI ilovasi.

`create_app()` — ilovani yig'adigan yagona joy (testlarda ham shu ishlatiladi).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import engine, get_session
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import request_context_middleware
from app.core.redis import close_redis
from app.modules.accounts.router import router as accounts_router
from app.modules.audit.router import history_router as audit_history_router
from app.modules.audit.router import router as audit_router
from app.modules.auth.router import router as auth_router
from app.modules.employees.router import router as employees_router

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    # Ilova to'xtaganda barcha ulanishlar toza yopiladi
    await engine.dispose()
    await close_redis()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, json_logs=settings.is_production)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if settings.is_production else "/docs",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(request_context_middleware)
    register_exception_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    api.include_router(auth_router)
    api.include_router(employees_router)
    api.include_router(accounts_router)
    api.include_router(audit_router)
    api.include_router(audit_history_router)
    app.include_router(api)

    # Xodim rasmlari ochiq havola orqali (E-012). Fayl nomlari tasodifiy.
    media_root = Path(settings.media_root)
    media_root.mkdir(parents=True, exist_ok=True)
    app.mount(settings.media_url, StaticFiles(directory=media_root), name="media")

    @app.get("/health", tags=["system"])
    async def health(session: AsyncSession = Depends(get_session)) -> JSONResponse:
        """Ilova va baza ishlayaptimi — monitoring uchun."""
        try:
            await session.execute(text("SELECT 1"))
        except Exception:
            return JSONResponse(status_code=503, content={"status": "error", "database": "down"})
        return JSONResponse(content={"status": "ok", "database": "ok"})

    return app


app = create_app()
