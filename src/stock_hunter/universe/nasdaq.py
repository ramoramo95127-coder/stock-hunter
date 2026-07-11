import csv
from io import StringIO

import httpx

from stock_hunter.universe.models import UniverseSymbol

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
EXCLUDED_NAME_MARKERS = (
    " warrant",
    " warrants",
    " unit",
    " units",
    " right",
    " rights",
    " preferred",
    " depositary share",
)


def parse_pipe_file(text: str, *, nasdaq: bool) -> list[UniverseSymbol]:
    reader = csv.DictReader(StringIO(text), delimiter="|")
    results = []
    for row in reader:
        symbol_key = "Symbol" if nasdaq else "ACT Symbol"
        symbol = (row.get(symbol_key) or "").strip().upper()
        name = (row.get("Security Name") or "").strip()
        if not symbol or symbol.startswith("FILE CREATION TIME"):
            continue
        exchange = "NASDAQ" if nasdaq else _exchange_name(row.get("Exchange", ""))
        results.append(
            UniverseSymbol(
                symbol=symbol,
                name=name,
                exchange=exchange,
                is_etf=(row.get("ETF") or "N").strip() == "Y",
            )
        )
    return results


def _exchange_name(code: str) -> str:
    return {"N": "NYSE", "A": "NYSE AMERICAN", "P": "NYSE ARCA", "Z": "BATS"}.get(
        code.strip(), code.strip() or "OTHER"
    )


def is_common_stock(item: UniverseSymbol) -> bool:
    name = item.name.lower()
    return (
        item.exchange in {"NASDAQ", "NYSE", "NYSE AMERICAN"}
        and not item.is_etf
        and not any(marker in name for marker in EXCLUDED_NAME_MARKERS)
        and not item.symbol.endswith(("W", "R", "U"))
        and "test issue" not in name
    )


class NasdaqUniverseSource:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=20, follow_redirects=True)

    async def fetch(self) -> list[UniverseSymbol]:
        nasdaq_response, other_response = await self._fetch_both()
        return parse_pipe_file(nasdaq_response, nasdaq=True) + parse_pipe_file(
            other_response, nasdaq=False
        )

    async def _fetch_both(self) -> tuple[str, str]:
        nasdaq = await self._client.get(NASDAQ_LISTED_URL)
        other = await self._client.get(OTHER_LISTED_URL)
        nasdaq.raise_for_status()
        other.raise_for_status()
        return nasdaq.text, other.text

    async def close(self) -> None:
        await self._client.aclose()
