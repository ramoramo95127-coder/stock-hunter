from stock_hunter.providers.base import FilingsProvider, MarketDataProvider, NewsProvider
from stock_hunter.providers.models import CompanyProfile, Filing, NewsItem, Quote


class MockProvider(MarketDataProvider, NewsProvider, FilingsProvider):
    name = "mock"

    async def quote(self, symbol: str) -> Quote:
        return Quote(symbol=symbol.upper(), price=10, source=self.name)

    async def profile(self, symbol: str) -> CompanyProfile:
        return CompanyProfile(
            symbol=symbol.upper(), name=f"{symbol.upper()} Corp", source=self.name
        )

    async def company_news(self, symbol: str) -> list[NewsItem]:
        return []

    async def recent_filings(self, cik: str) -> list[Filing]:
        return []
