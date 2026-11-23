"""Xodimlar va Lavozimlar endpoint'lari. Faqat superadmin va admin (17-band)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.pagination import Page, PageParams, page_params
from app.core.roles import Role
from app.modules.auth.dependencies import require_roles
from app.modules.auth.service import CurrentUser
from app.modules.employees.schemas import (
    EmployeeCreate,
    EmployeeOut,
    EmployeeStatus,
    EmployeeUpdate,
    PositionChange,
    PositionOut,
    RoleOut,
)
from app.modules.employees.service import EmployeeService

router = APIRouter(tags=["Xodimlar"])

_admin = require_roles(Role.ADMIN)


def get_service(
    session: AsyncSession = Depends(get_session), actor: CurrentUser = Depends(_admin)
) -> EmployeeService:
    return EmployeeService(session, actor)


Service = Annotated[EmployeeService, Depends(get_service)]


@router.get("/roles", response_model=list[RoleOut], summary="Lavozimlar ma'lumotnomasi")
async def roles(service: Service) -> list[RoleOut]:
    return await service.roles_directory()


@router.get("/employees", response_model=Page[EmployeeOut], summary="Xodimlar ro'yxati")
async def list_employees(
    service: Service,
    params: Annotated[PageParams, Depends(page_params)],
    status_: Annotated[EmployeeStatus, Query(alias="status")] = EmployeeStatus.ACTIVE,
    search: Annotated[str | None, Query(max_length=100, description="Ism yoki familiya")] = None,
    role: Role | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
) -> Page[EmployeeOut]:
    """`status=archived` — "Arxiv" bo'limi. Standart tartib: oxirgi qo'shilgan birinchi."""
    return await service.search(
        params,
        status=status_,
        text_query=search,
        role=role,
        created_from=created_from,
        created_to=created_to,
    )


@router.post(
    "/employees",
    response_model=EmployeeOut,
    status_code=status.HTTP_201_CREATED,
    summary="Yangi xodim",
)
async def create_employee(
    service: Service,
    data: Annotated[EmployeeCreate, Form()],
    photo: Annotated[UploadFile, File(description="JPG yoki PNG, 5 MB gacha")],
) -> EmployeeOut:
    """Forma (multipart): hamma maydon majburiy, rasm ham (E-001)."""
    return await service.create(data, await photo.read())


@router.get("/employees/{employee_id}", response_model=EmployeeOut, summary="Xodim kartochkasi")
async def get_employee(employee_id: int, service: Service) -> EmployeeOut:
    return await service.get(employee_id)


@router.patch("/employees/{employee_id}", response_model=EmployeeOut, summary="Tahrirlash")
async def update_employee(employee_id: int, data: EmployeeUpdate, service: Service) -> EmployeeOut:
    return await service.update(employee_id, data)


@router.put(
    "/employees/{employee_id}/photo", response_model=EmployeeOut, summary="Rasmni almashtirish"
)
async def replace_photo(
    employee_id: int, service: Service, photo: Annotated[UploadFile, File()]
) -> EmployeeOut:
    return await service.replace_photo(employee_id, await photo.read())


@router.post(
    "/employees/{employee_id}/position",
    response_model=EmployeeOut,
    summary="Lavozim / maoshni o'zgartirish",
)
async def change_position(
    employee_id: int, change: PositionChange, service: Service
) -> EmployeeOut:
    """Kadrlar ko'chirilishi. Lavozim o'zgarsa — xodim barcha qurilmalardan chiqariladi."""
    return await service.change_position(employee_id, change)


@router.get(
    "/employees/{employee_id}/positions",
    response_model=list[PositionOut],
    summary="Lavozim va maosh tarixi",
)
async def positions(employee_id: int, service: Service) -> list[PositionOut]:
    return await service.positions(employee_id)


@router.post("/employees/{employee_id}/archive", response_model=EmployeeOut, summary="Arxivlash")
async def archive(employee_id: int, service: Service) -> EmployeeOut:
    return await service.archive(employee_id)


@router.post(
    "/employees/{employee_id}/restore", response_model=EmployeeOut, summary="Arxivdan qaytarish"
)
async def restore(employee_id: int, service: Service) -> EmployeeOut:
    return await service.restore(employee_id)


@router.delete(
    "/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT, summary="O'chirish"
)
async def delete_employee(employee_id: int, service: Service) -> None:
    """Tarixi yo'q — butunlay o'chadi. Tarixi bor — shaxsiy ma'lumotlari o'chiriladi."""
    await service.delete(employee_id)
