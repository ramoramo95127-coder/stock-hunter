from abc import ABC, abstractmethod

from stock_hunter.providers.models import CompanyProfile, Filing, NewsItem, Quote


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    async def quote(self, symbol: str) -> Quote: ...
    @abstractmethod
    async def profile(self, symbol: str) -> CompanyProfile: ...
    async def close(self) -> None:
        return None


class NewsProvider(ABC):
    name: str

    @abstractmethod
    async def company_news(self, symbol: str) -> list[NewsItem]: ...


class FilingsProvider(ABC):
    name: str

    @abstractmethod
    async def recent_filings(self, cik: str) -> list[Filing]: ...
