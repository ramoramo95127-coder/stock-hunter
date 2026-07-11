from stock_hunter.config import Settings
from stock_hunter.providers.base import MarketDataProvider
from stock_hunter.providers.finnhub import FinnhubProvider
from stock_hunter.providers.fmp import FmpProvider
from stock_hunter.providers.mock import MockProvider


def create_market_provider(settings: Settings) -> MarketDataProvider:
    if settings.default_provider == "mock":
        return MockProvider()
    if settings.default_provider == "fmp" and settings.fmp_api_key:
        return FmpProvider(settings.fmp_api_key)
    if settings.default_provider == "finnhub" and settings.finnhub_api_key:
        return FinnhubProvider(settings.finnhub_api_key)
    raise ValueError("Configured provider is unavailable or missing its API key")
