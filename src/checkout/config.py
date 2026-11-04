"""Application settings, loaded from environment variables and an optional .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "checkout"
    debug: bool = False
    database_url: str = "mysql+pymysql://app:changeme@localhost:3306/app?charset=utf8mb4"


@lru_cache
def get_settings() -> Settings:
    return Settings()
