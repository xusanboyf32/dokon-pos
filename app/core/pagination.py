"""Offset pagination (docs/API_CONVENTIONS.md, 4-bo'lim).

GET /api/v1/employees?page=2&size=20
→ {"items": [...], "total": 134, "page": 2, "size": 20, "pages": 7}
"""

from dataclasses import dataclass
from math import ceil
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel


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
