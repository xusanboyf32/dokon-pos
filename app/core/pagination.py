"""Pagination (docs/API_CONVENTIONS.md, 4-bo'lim): offset va cursor.

GET /api/v1/employees?page=2&size=20
→ {"items": [...], "total": 134, "page": 2, "size": 20, "pages": 7}
"""

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from math import ceil
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

from app.core.exceptions import AppError


@dataclass(frozen=True, slots=True)
class PageParams:
    page: int
    size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def page_params(
    page: int = Query(1, ge=1, description="Sahifa raqami (1 dan boshlanadi)"),
    size: int = Query(20, ge=1, le=100, description="Sahifadagi yozuvlar soni (ko'pi bilan 100)"),
) -> PageParams:
    return PageParams(page=page, size=size)


T = TypeVar("T")


class Page(BaseModel, Generic[T]):  # Python 3.11: Page[T] sintaksisi hali yo'q
    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def build(cls, items: list[T], total: int, params: PageParams) -> "Page[T]":
        return cls(
            items=items,
            total=total,
            page=params.page,
            size=params.size,
            pages=ceil(total / params.size) if total else 0,
        )


# ================================================================== cursor (keyset)
# Katta ro'yxatlar uchun (audit jurnali, cheklar):
#
# GET /api/v1/audit-logs?limit=50&cursor=...
# → {"items": [...], "next_cursor": "...", "has_more": true}
#
# OFFSET 100000 bo'lsa baza 100 000 qatorni o'qib tashlab yuboradi — sahifa sekinlashadi.
# Cursor esa "oxirgi ko'rilgan (vaqt, id) dan keyingilar" deydi va indeks bo'yicha
# to'g'ridan-to'g'ri o'sha joyga sakraydi: 1-sahifa ham, 10 000-sahifa ham bir xil tez.
# "Jami nechta" (COUNT) qaytarilmaydi — katta jadvalda u ham sekin.


class InvalidCursorError(AppError):
    status_code = 422
    code = "INVALID_CURSOR"
    message = "Sahifa belgisi (cursor) noto'g'ri"


@dataclass(frozen=True, slots=True)
class CursorParams:
    limit: int
    after: tuple[datetime, int] | None  # (vaqt, id) — oxirgi ko'rilgan yozuv


def encode_cursor(moment: datetime, row_id: int) -> str:
    raw = f"{moment.isoformat()}|{row_id}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        moment_raw, id_raw = base64.urlsafe_b64decode(padded).decode().split("|")
        moment = datetime.fromisoformat(moment_raw)
        if moment.tzinfo is None:
            raise ValueError("timezone yo'q")
        return moment, int(id_raw)
    except (ValueError, UnicodeDecodeError, binascii.Error) as error:
        raise InvalidCursorError() from error


def cursor_params(
    limit: int = Query(50, ge=1, le=100, description="Nechta yozuv (ko'pi bilan 100)"),
    cursor: str | None = Query(None, description="Oldingi javobdagi `next_cursor`"),
) -> CursorParams:
    return CursorParams(limit=limit, after=decode_cursor(cursor) if cursor else None)


class CursorPage(BaseModel, Generic[T]):
    items: list[T]
    next_cursor: str | None
    has_more: bool
