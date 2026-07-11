from pydantic import SecretStr

from stock_hunter.providers.base import MarketDataProvider
from stock_hunter.providers.http import HttpProvider, ProviderError
from stock_hunter.providers.models import CompanyProfile, Quote


class FmpProvider(HttpProvider, MarketDataProvider):
    name = "fmp"

    def __init__(self, api_key: SecretStr) -> None:
        super().__init__("https://financialmodelingprep.com")
        self._key = api_key if isinstance(api_key, SecretStr) else SecretStr(api_key)

    async def quote(self, symbol: str) -> Quote:
        data = await self._get(
            f"/stable/quote/{symbol.upper()}", {"apikey": self._key.get_secret_value()}
        )
        if not isinstance(data, list) or not data:
            raise ProviderError("FMP returned no quote")
        return Quote(symbol=symbol.upper(), price=float(data[0]["price"]), source=self.name)

    async def profile(self, symbol: str) -> CompanyProfile:
        data = await self._get(
            f"/stable/profile/{symbol.upper()}", {"apikey": self._key.get_secret_value()}
        )
        if not isinstance(data, list) or not data:
            raise ProviderError("FMP returned no profile")
        item = data[0]
        return CompanyProfile(
            symbol=symbol.upper(),
            name=item.get("companyName") or symbol.upper(),
            exchange=item.get("exchange"),
            market_cap=item.get("marketCap"),
            source=self.name,
        )
