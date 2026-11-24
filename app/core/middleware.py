"""So'rov konteksti: har so'rovga `request_id` beriladi va loglanadi.

Xato bo'lganda foydalanuvchi `request_id` ni aytadi — logdan aynan o'sha so'rov topiladi.
"""

from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import Request, Response

from app.core.request_context import RequestContext, set_request_context

log = structlog.get_logger()


async def request_context_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id
    set_request_context(
        RequestContext(
            request_id=request_id[:64],  # mijoz juda uzun ID yuborsa ham ustunga sig'adi
            ip=request.client.host if request.client else None,
            user_agent=(request.headers.get("user-agent") or "")[:255] or None,
        )
    )

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id, method=request.method, path=request.url.path
    )

    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("request_failed")
        raise

    duration_ms = round((perf_counter() - started) * 1000, 1)
    response.headers["X-Request-ID"] = request_id
    log.info("request", status=response.status_code, duration_ms=duration_ms)
    return response
