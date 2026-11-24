"""🔔 Muammolar endpoint'lari (N-001, N-004)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.pagination import Page, PageParams, page_params
from app.core.roles import Role
from app.modules.auth.dependencies import require_roles
from app.modules.auth.service import CurrentUser
from app.modules.problems.models import ProblemType
from app.modules.problems.schemas import ProblemCountOut, ProblemOut, ProblemStatusFilter
from app.modules.problems.service import ProblemService

router = APIRouter(prefix="/problems", tags=["Muammolar"])

_admin = require_roles(Role.ADMIN)  # superadmin har doim kiradi


def get_service(
    session: AsyncSession = Depends(get_session), viewer: CurrentUser = Depends(_admin)
) -> ProblemService:
    return ProblemService(session, viewer)


Service = Annotated[ProblemService, Depends(get_service)]


@router.get("/count", response_model=ProblemCountOut, summary="🔔 Ochiq muammolar soni")
async def count_problems(service: Service) -> ProblemCountOut:
    return ProblemCountOut(open=await service.count_open())


@router.get("", response_model=Page[ProblemOut], summary="Muammolar ro'yxati")
async def list_problems(
    service: Service,
    params: Annotated[PageParams, Depends(page_params)],
    status: ProblemStatusFilter = Query(ProblemStatusFilter.OPEN, description="Standart: ochiq"),
    type: ProblemType | None = Query(None, description="Muammo turi"),  # noqa: A002
    employee_id: int | None = Query(None, description="Qaysi xodimga oid"),
    date_from: date | None = Query(None, description="Toshkent sanasi, shu kun ham kiradi"),
    date_to: date | None = Query(None, description="Toshkent sanasi, shu kun ham kiradi"),
) -> Page[ProblemOut]:
    """Eng yangisi tepada. Ochiq muammoda `action` — tezkor tugma (masalan, "Blokni ochish")."""
    return await service.search(
        params,
        status=status,
        type_=type,
        employee_id=employee_id,
        date_from=date_from,
        date_to=date_to,
    )
