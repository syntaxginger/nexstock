from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    gemini_api_key: str = ""
    line_channel_access_token: str = ""
    line_channel_secret: str = ""
    line_user_id: str = ""

    app_env: str = "development"
    database_url: str = "sqlite+aiosqlite:///./nexstock.db"
    morning_brief_hour: int = 8
    morning_brief_minute: int = 0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
