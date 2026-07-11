import asyncio
import logging

import httpx
from pydantic import BaseModel, SecretStr

logger = logging.getLogger(__name__)


class RadarCandidate(BaseModel):
    symbol: str
    price: float
    change_percent: float
    volume: int = 0


class FmpRadar:
    def __init__(
        self, api_key: SecretStr, min_price: float, max_price: float, max_symbols: int = 50
    ) -> None:
        self.key = api_key
        self.min_price = min_price
        self.max_price = max_price
        self.max_symbols = max_symbols
        self._client = httpx.AsyncClient(base_url="https://financialmodelingprep.com", timeout=15)

    async def candidates(self) -> list[RadarCandidate]:
        response = await self._client.get(
            "/stable/biggest-gainers", params={"apikey": self.key.get_secret_value()}
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            return []
        parsed = []
        for item in data:
            symbol, price = str(item.get("symbol") or "").upper(), float(item.get("price") or 0)
            change = float(item.get("changesPercentage") or item.get("changePercentage") or 0)
            if symbol and self.min_price <= price <= self.max_price:
                parsed.append(
                    RadarCandidate(
                        symbol=symbol,
                        price=price,
                        change_percent=change,
                        volume=int(item.get("volume") or 0),
                    )
                )
        return sorted(parsed, key=lambda item: (item.change_percent, item.volume), reverse=True)[
            : self.max_symbols
        ]

    async def close(self) -> None:
        await self._client.aclose()


async def run_radar(
    radar: FmpRadar, collector, manual_symbols: list[str], refresh_seconds: int, stop: asyncio.Event
) -> None:
    while not stop.is_set():
        try:
            candidates = await radar.candidates()
            symbols = list(dict.fromkeys([*(item.symbol for item in candidates), *manual_symbols]))
            collector.set_symbols(symbols)
            logger.info("Radar selected %s symbols", len(symbols))
        except Exception:
            logger.exception("Radar refresh failed; keeping current subscriptions")
        try:
            await asyncio.wait_for(stop.wait(), timeout=refresh_seconds)
        except TimeoutError:
            pass
