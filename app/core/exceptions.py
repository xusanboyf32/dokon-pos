"""Yagona xato formati.

Service qatlami `AppError` (yoki uning vorislari)ni ko'taradi.
Global handler uni hamma joyda bir xil JSON'ga o'giradi:

    {"error": {"code": "...", "message": "...", "details": {...}, "request_id": "..."}}
"""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = structlog.get_logger()


class AppError(Exception):
    status_code: int = 400
    code: str = "BAD_REQUEST"
    message: str = "So'rovda xatolik"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        super().__init__(self.message)


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    message = "Tizimga kirish talab qilinadi"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"
    message = "Bu amal uchun ruxsat yo'q"


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Topilmadi"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "Ma'lumot to'qnashuvi"


def _error_body(
    request: Request, code: str, message: str, details: dict[str, Any]
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": getattr(request.state, "request_id", None),
        }
    }


async def _app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(request, exc.code, exc.message, exc.details),
    )


# Pydantic'ning inglizcha xabarlari o'rniga o'zbekcha (eng ko'p uchraydiganlari).
# Bu yerda yo'q tur — Pydantic xabari o'zgarishsiz qoladi.
_UZ_MESSAGES: dict[str, str] = {
    "missing": "Bu maydon majburiy",
    "string_too_short": "Juda qisqa",
    "string_too_long": "Juda uzun",
    "string_type": "Matn bo'lishi kerak",
    "int_parsing": "Butun son bo'lishi kerak",
    "int_type": "Butun son bo'lishi kerak",
    "decimal_parsing": "Son bo'lishi kerak",
    "decimal_type": "Son bo'lishi kerak",
    "decimal_max_places": "Ko'pi bilan 2 ta kasr xona (tiyin)",
    "date_parsing": "Sana YYYY-MM-DD ko'rinishida bo'lishi kerak",
    "date_from_datetime_parsing": "Sana YYYY-MM-DD ko'rinishida bo'lishi kerak",
    "bool_parsing": "true yoki false bo'lishi kerak",
    "enum": "Ruxsat etilmagan qiymat",
    "greater_than_equal": "Juda kichik qiymat",
    "less_than_equal": "Juda katta qiymat",
}


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = exc.errors()

    # So'rov matni JSON sifatida o'qilmadi (qavs yopilmagan, ortiqcha vergul...) —
    # maydonlar bo'yicha emas, bitta tushunarli xabar
    broken = next((e for e in errors if e["type"] == "json_invalid"), None)
    if broken is not None:
        loc = broken["loc"]
        position = loc[1] if len(loc) > 1 else None
        return JSONResponse(
            status_code=422,
            content=_error_body(
                request,
                "INVALID_JSON",
                "So'rov matni noto'g'ri yozilgan (JSON). Qavslar, qo'shtirnoq va vergullarni "
                "tekshiring",
                {"position": position},
            ),
        )

    fields = [
        {
            "field": ".".join(str(p) for p in err["loc"][1:]),
            # O'zimizning validator xabari (Pydantic unga "Value error, " qo'shadi) yoki tarjima
            "message": (
                str(err["msg"]).removeprefix("Value error, ")
                if err["type"] == "value_error"
                else _UZ_MESSAGES.get(err["type"], str(err["msg"]))
            ),
        }
        for err in errors
    ]
    return JSONResponse(
        status_code=422,
        content=_error_body(
            request, "VALIDATION_ERROR", "Ma'lumotlar noto'g'ri", {"fields": fields}
        ),
    )


_HTTP_ERRORS: dict[int, tuple[str, str]] = {
    404: ("NOT_FOUND", "Bunday manzil topilmadi"),
    405: ("METHOD_NOT_ALLOWED", "Bu manzil uchun bunday so'rov turi qo'llanmaydi"),
}


async def _http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """FastAPI'ning o'z xatolari (masalan, mavjud bo'lmagan manzil) ham yagona formatda."""
    assert isinstance(exc, StarletteHTTPException)
    code, message = _HTTP_ERRORS.get(exc.status_code, ("HTTP_ERROR", str(exc.detail)))
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(request, code, message, {}),
        headers=getattr(exc, "headers", None),
    )


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Tafsilot faqat logga yoziladi, foydalanuvchiga ko'rsatilmaydi
    log.exception("unhandled_error", path=request.url.path)
    return JSONResponse(
        status_code=500,
        content=_error_body(request, "INTERNAL_ERROR", "Ichki xatolik yuz berdi", {}),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
