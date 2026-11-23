"""Auth API sxemalari (kiruvchi va chiquvchi ma'lumot)."""

from pydantic import BaseModel, Field

from app.core.roles import Role


class LoginRequest(BaseModel):
    # Login'da formatni qattiq tekshirmaymiz (noto'g'ri format ham "login yoki parol xato"
    # bo'lishi kerak) — faqat haddan tashqari uzun ma'lumotdan himoya.
    username: str = Field(min_length=1, max_length=50, examples=["anvar"])
    password: str = Field(min_length=1, max_length=64, examples=["1234"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token necha soniya amal qiladi")
    # Frontend shu bo'yicha foydalanuvchini o'z sahifasiga yo'naltiradi (6-band)
    role: Role


class MeResponse(BaseModel):
    account_id: int
    role: Role
    employee_id: int | None
