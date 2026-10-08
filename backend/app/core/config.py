from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./dev.db"
    bot_token: str = ""
    admin_telegram_ids: str = ""
    jwt_secret: str = "dev-secret-change-me"
    fernet_key: str = ""
    host: str = "0.0.0.0"
    port: int = 8000
    cookie_secure: bool = False
    timezone: str = "Asia/Tashkent"

    block_minutes: int = 40
    lead_seconds: int = 60  # keyingi blok tugashiga necha soniya qolganda yuboriladi
    max_blocks: int = 10
    account_buffer_minutes: int = 3
    jwt_hours: int = 12

    @field_validator("admin_telegram_ids")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def admin_ids(self) -> list[int]:
        return [int(x) for x in self.admin_telegram_ids.split(",") if x.strip().isdigit()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
