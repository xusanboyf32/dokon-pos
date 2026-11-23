"""FastAPI dependency'lari: "kim bu?" va "ruxsat bormi?".

Boshqa modullar endpoint'larni shular bilan himoyalaydi:

    @router.get("/employees")
    async def list_employees(user: CurrentUser = Depends(require_roles(Role.ADMIN))): ...
"""

from collections.abc import Awaitable, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.roles import Role
from app.modules.auth.service import AuthService, CurrentUser

# auto_error=False: token yo'q bo'lsa FastAPI'ning o'z 403 xatosi emas,
# bizning yagona formatdagi 401 xatomiz qaytadi
_bearer = HTTPBearer(auto_error=False)


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    return AuthService(session)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    service: AuthService = Depends(get_auth_service),
) -> CurrentUser:
    if credentials is None:
        raise UnauthorizedError()
    return await service.authenticate(credentials.credentials)


def require_roles(*roles: Role) -> Callable[..., Awaitable[CurrentUser]]:
    """Faqat ko'rsatilgan rollar kira oladi. Superadmin har doim kira oladi (15-band)."""
    allowed = frozenset(roles) | {Role.SUPERADMIN}

    async def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise ForbiddenError()
        return user

    return checker
