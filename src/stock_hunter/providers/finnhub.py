from pydantic import SecretStr

from stock_hunter.providers.base import MarketDataProvider, NewsProvider
from stock_hunter.providers.http import HttpProvider, ProviderError
from stock_hunter.providers.models import CompanyProfile, NewsItem, Quote


class FinnhubProvider(HttpProvider, MarketDataProvider, NewsProvider):
    name = "finnhub"

    def __init__(self, api_key: SecretStr) -> None:
        super().__init__("https://finnhub.io/api/v1")
        self._key = api_key if isinstance(api_key, SecretStr) else SecretStr(api_key)

    def params(self, **values: str) -> dict[str, str]:
        return {**values, "token": self._key.get_secret_value()}

    async def quote(self, symbol: str) -> Quote:
        data = await self._get("/quote", self.params(symbol=symbol.upper()))
        if not isinstance(data, dict) or not data.get("c"):
            raise ProviderError("Finnhub returned no quote")
        return Quote(symbol=symbol.upper(), price=float(data["c"]), source=self.name)

    async def profile(self, symbol: str) -> CompanyProfile:
        data = await self._get("/stock/profile2", self.params(symbol=symbol.upper()))
        if not isinstance(data, dict) or not data:
            raise ProviderError("Finnhub returned no profile")
        return CompanyProfile(
            symbol=symbol.upper(),
            name=data.get("name") or symbol.upper(),
            exchange=data.get("exchange"),
            market_cap=data.get("marketCapitalization"),
            source=self.name,
        )

    async def company_news(self, symbol: str) -> list[NewsItem]:
        return []
