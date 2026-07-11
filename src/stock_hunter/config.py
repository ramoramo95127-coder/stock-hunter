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
    universe_min_price: float = 1.0
    universe_max_price: float = 30.0
    universe_min_market_cap: float = 20_000_000
    universe_max_market_cap: float = 5_000_000_000
    universe_refresh_hour_utc: int = 12


@lru_cache
def get_settings() -> Settings:
    return Settings()
