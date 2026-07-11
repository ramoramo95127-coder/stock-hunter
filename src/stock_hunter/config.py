from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://stock_hunter:stock_hunter@postgres/stock_hunter"
    redis_url: str = "redis://redis:6379/0"
    default_provider: str = "mock"
    fmp_api_key: SecretStr | None = None
    finnhub_api_key: SecretStr | None = None
    sec_user_agent: str = "StockHunter personal-app contact@example.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
