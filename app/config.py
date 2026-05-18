from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = Field(..., alias="BOT_TOKEN")
    bot_username: str = Field("имя_бота", alias="BOT_USERNAME")
    database_url: str = Field(..., alias="DATABASE_URL")

    daily_delivery_time: str = Field("17:00", alias="DAILY_DELIVERY_TIME")
    daily_delivery_timezone: str = Field("Europe/Moscow", alias="DAILY_DELIVERY_TIMEZONE")
    daily_questions_count: int = Field(5, alias="DAILY_QUESTIONS_COUNT")

    default_language: str = Field("ru", alias="DEFAULT_LANGUAGE")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    assets_dir: Path = Field(Path("/app/assets"), alias="ASSETS_DIR")

    # Inline-mode static-image server. When `inline_public_base_url` is set,
    # inline results use InlineQueryResultPhoto with HTTPS URLs — Telegram
    # fetches each flag from the URL on demand, so no /preload_inline / no
    # 40-photo bootstrap is needed.
    inline_public_base_url: str | None = Field(None, alias="INLINE_PUBLIC_BASE_URL")
    web_port: int = Field(8080, alias="WEB_PORT")

    @field_validator("daily_delivery_time")
    @classmethod
    def _validate_time(cls, v: str) -> str:
        hour, minute = v.split(":")
        h, m = int(hour), int(minute)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError(f"invalid daily_delivery_time: {v}")
        return v

    @property
    def daily_delivery_hour(self) -> int:
        return int(self.daily_delivery_time.split(":")[0])

    @property
    def daily_delivery_minute(self) -> int:
        return int(self.daily_delivery_time.split(":")[1])

    @property
    def flags_dir(self) -> Path:
        return self.assets_dir / "flags"


settings = Settings()  # type: ignore[call-arg]
