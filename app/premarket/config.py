"""Application settings and logging configuration."""
from __future__ import annotations

import logging
from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    database_url: str = Field(
        default="postgresql+psycopg://premarket:premarket@db:5432/premarket",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://cache:6379/0", alias="REDIS_URL")
    deepinfra_api_key: str = Field(default="", alias="DEEPINFRA_API_KEY")
    deepinfra_base_url: str = Field(
        default="https://api.deepinfra.com/v1/openai", alias="DEEPINFRA_BASE_URL"
    )
    llm_model: str = Field(
        default="meta-llama/Meta-Llama-3.1-70B-Instruct", alias="LLM_MODEL"
    )
    timezone: str = Field(default="Asia/Kolkata", alias="TIMEZONE")
    demo_mode: bool = Field(default=False, alias="DEMO_MODE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def configure_logging(level: str | None = None) -> None:
    """Configure root logger. Called once at startup."""
    settings = get_settings()
    log_level = (level or settings.log_level).upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    # Quiet third-party noise.
    for noisy in ("yfinance", "peewee", "urllib3", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
