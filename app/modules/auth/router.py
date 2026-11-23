"""Auth endpoint'lari. Router faqat HTTP bilan ishlaydi — mantiq service'da."""

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from app.core.config import get_settings
from app.modules.auth.dependencies import get_auth_service, get_current_user
from app.modules.auth.exceptions import SessionInvalidError
from app.modules.auth.schemas import LoginRequest, MeResponse, TokenResponse
from app.modules.auth.service import AuthService, CurrentUser, TokenPair

router = APIRouter(prefix="/auth", tags=["Auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"  # cookie faqat auth endpoint'lariga yuboriladi


def _client(request: Request) -> dict[str, str | None]:
    return {
        "ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


def _set_refresh_cookie(response: Response, pair: TokenPair) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=pair.refresh_token,
        expires=pair.refresh_expires_at,
        httponly=True,  # JavaScript o'qiy olmaydi (XSS)
        secure=settings.is_production,  # production'da faqat HTTPS
        samesite="strict",  # boshqa saytdan kelgan so'rovga qo'shilmaydi (CSRF)
        path=REFRESH_COOKIE_PATH,
    )


def _token_response(pair: TokenPair) -> TokenResponse:
    return TokenResponse(
        access_token=pair.access_token,
        expires_in=get_settings().access_token_minutes * 60,
        role=pair.role,
    )


@router.post("/login", response_model=TokenResponse, summary="Tizimga kirish")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Username + parol → access token (javobda) va refresh token (httpOnly cookie)."""
    pair = await service.login(body.username, body.password, **_client(request))
    _set_refresh_cookie(response, pair)
    return _token_response(pair)


@router.post("/refresh", response_model=TokenResponse, summary="Access token'ni yangilash")
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """Frontend buni access token eskirganda fonda chaqiradi — foydalanuvchi sezmaydi."""
    if not refresh_token:
        raise SessionInvalidError()
    pair = await service.refresh(refresh_token, **_client(request))
    _set_refresh_cookie(response, pair)
    return _token_response(pair)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Chiqish")
async def logout(
    response: Response,
    user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
) -> None:
    await service.logout(user.session_id)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


@router.get("/me", response_model=MeResponse, summary="Men kimman")
async def me(user: CurrentUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(account_id=user.account_id, role=user.role, employee_id=user.employee_id)
