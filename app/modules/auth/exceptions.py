"""Auth xatolari. Xabarlar spetsifikatsiyadagi matnlar bilan bir xil (A-018)."""

from app.core.exceptions import AppError, UnauthorizedError


class InvalidCredentialsError(UnauthorizedError):
    # Username yoki parol — qaysi biri xatoligi AYTILMAYDI (7-band)
    code = "INVALID_CREDENTIALS"
    message = "Login yoki parol xato"


class AccountLockedError(AppError):
    status_code = 423
    code = "ACCOUNT_LOCKED"
    message = "Hisob bloklandi, administratorga murojaat qiling"


class SessionInvalidError(UnauthorizedError):
    code = "SESSION_INVALID"
    message = "Sessiya yaroqsiz, qaytadan kiring"


class SessionExpiredError(UnauthorizedError):
    code = "SESSION_EXPIRED"
    message = "Sessiya muddati tugadi, qaytadan kiring"


class RefreshTokenReusedError(UnauthorizedError):
    code = "REFRESH_TOKEN_REUSED"
    message = "Xavfsizlik sababli barcha qurilmalardan chiqarildingiz, qaytadan kiring"
