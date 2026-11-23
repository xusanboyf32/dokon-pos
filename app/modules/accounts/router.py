""" "Parollar" bo'limi endpoint'lari. Faqat superadmin va admin."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.pagination import Page, PageParams, page_params
from app.core.roles import Role
from app.modules.accounts.schemas import (
    AccountCreate,
    AccountOut,
    AccountStatusFilter,
    PasswordReset,
)
from app.modules.accounts.service import AccountService
from app.modules.auth.dependencies import get_login_guard, require_roles
from app.modules.auth.lockout import LoginGuard
from app.modules.auth.service import CurrentUser

router = APIRouter(prefix="/accounts", tags=["Parollar"])

_admin = require_roles(Role.ADMIN)


def get_service(
    session: AsyncSession = Depends(get_session),
    actor: CurrentUser = Depends(_admin),
    guard: LoginGuard = Depends(get_login_guard),
) -> AccountService:
    return AccountService(session, actor, guard)


Service = Annotated[AccountService, Depends(get_service)]


@router.get("", response_model=Page[AccountOut], summary="Loginlar ro'yxati")
async def list_accounts(
    service: Service,
    params: Annotated[PageParams, Depends(page_params)],
    status_: Annotated[AccountStatusFilter, Query(alias="status")] = AccountStatusFilter.ACTIVE,
    search: Annotated[
        str | None, Query(max_length=100, description="Username yoki xodim ismi")
    ] = None,
    role: Role | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
) -> Page[AccountOut]:
    """Har qatorda holat: faol / vaqtincha blok (qachongacha) / doimiy blok / o'chirilgan."""
    return await service.search(
        params,
        status=status_,
        text_query=search,
        role=role,
        created_from=created_from,
        created_to=created_to,
    )


@router.post(
    "", response_model=AccountOut, status_code=status.HTTP_201_CREATED, summary="Login yaratish"
)
async def create_account(data: AccountCreate, service: Service) -> AccountOut:
    return await service.create(data)


@router.get("/{account_id}", response_model=AccountOut, summary="Login kartochkasi")
async def get_account(account_id: int, service: Service) -> AccountOut:
    return await service.get(account_id)


@router.post(
    "/{account_id}/reset-password", response_model=AccountOut, summary="Parolni almashtirish"
)
async def reset_password(account_id: int, data: PasswordReset, service: Service) -> AccountOut:
    """Xodim barcha qurilmalardan chiqariladi va yangi parol bilan kiradi."""
    return await service.reset_password(account_id, data)


@router.post("/{account_id}/unlock", response_model=AccountOut, summary="Blokni ochish")
async def unlock(account_id: int, service: Service) -> AccountOut:
    return await service.unlock(account_id)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Loginni o'chirish")
async def delete_account(account_id: int, service: Service) -> None:
    """Xodim va tarix qoladi. Qaytarib bo'lmaydi — kerak bo'lsa yangi login yaratiladi."""
    await service.delete(account_id)
