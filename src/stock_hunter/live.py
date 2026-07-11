import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import websockets
from pydantic import SecretStr

from stock_hunter.providers.models import MinuteBarData

logger = logging.getLogger(__name__)


class MinuteAggregator:
    def __init__(self, source: str = "finnhub") -> None:
        self.source = source
        self._bars: dict[str, MinuteBarData] = {}

    def add_trade(
        self, symbol: str, price: float, volume: int, timestamp_ms: int
    ) -> MinuteBarData | None:
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000, UTC).replace(
            second=0, microsecond=0
        )
        symbol = symbol.upper()
        current = self._bars.get(symbol)
        completed = None
        if current and current.timestamp != timestamp:
            completed = current
            current = None
        if current is None:
            self._bars[symbol] = MinuteBarData(
                symbol=symbol,
                timestamp=timestamp,
                open=price,
                high=price,
                low=price,
                close=price,
                volume=volume,
                source=self.source,
            )
        else:
            current.high = max(current.high, price)
            current.low = min(current.low, price)
            current.close = price
            current.volume += volume
        return completed


class FinnhubLiveCollector:
    def __init__(
        self,
        token: SecretStr,
        symbols: list[str],
        on_bar: Callable[[MinuteBarData], Awaitable[None]],
    ) -> None:
        self.token = token
        self.symbols = symbols
        self.on_bar = on_bar
        self.aggregator = MinuteAggregator()

    async def run(self, stop: asyncio.Event) -> None:
        delay = 1
        while not stop.is_set():
            try:
                await self._connect(stop)
                delay = 1
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Finnhub stream disconnected; retrying")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=delay)
                except TimeoutError:
                    delay = min(delay * 2, 30)

    async def _connect(self, stop: asyncio.Event) -> None:
        url = f"wss://ws.finnhub.io?token={self.token.get_secret_value()}"
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as socket:
            for symbol in self.symbols:
                await socket.send(json.dumps({"type": "subscribe", "symbol": symbol}))
            while not stop.is_set():
                raw = await asyncio.wait_for(socket.recv(), timeout=30)
                message = json.loads(raw)
                for trade in message.get("data", []):
                    completed = self.aggregator.add_trade(
                        trade["s"], float(trade["p"]), int(trade["v"]), int(trade["t"])
                    )
                    if completed:
                        await self.on_bar(completed)
