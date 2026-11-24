"""Joriy so'rov haqida ma'lumot: request_id, IP, brauzer (user-agent).

Middleware har so'rov boshida to'ldiradi. Kodning istalgan joyi (masalan audit)
uni argument sifatida uzatmasdan oladi: `current_request()`.

ContextVar — har so'rov (async vazifa) o'z qiymatini ko'radi, ular aralashib ketmaydi.
So'rovdan tashqarida (CLI, Celery) qiymat bo'sh: `RequestContext()`.
"""

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestContext:
    request_id: str | None = None
    ip: str | None = None
    user_agent: str | None = None


_EMPTY = RequestContext()
_current: ContextVar[RequestContext] = ContextVar("request_context", default=_EMPTY)


def current_request() -> RequestContext:
    return _current.get()


def set_request_context(context: RequestContext) -> Token[RequestContext]:
    return _current.set(context)


def reset_request_context(token: Token[RequestContext]) -> None:
    _current.reset(token)
