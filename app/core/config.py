"""Ilova sozlamalari.

Barcha sozlamalar `.env` faylidan (yoki muhit o'zgaruvchilaridan) o'qiladi.
Kodda maxfiy qiymat bo'lmaydi.
"""

from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Do'kon POS"
    environment: Literal["local", "test", "production"] = "local"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # postgresql+asyncpg://user:parol@host:5432/baza
    database_url: PostgresDsn
    db_pool_size: int = 10
    db_max_overflow: int = 20
    # Osilib qolgan so'rov shuncha millisekunddan keyin to'xtatiladi
    db_statement_timeout_ms: int = 5000

    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Sozlamalar bir marta o'qiladi va keyin keshdan qaytariladi."""
    return Settings()  # majburiy qiymatlar (database_url) .env dan keladi
