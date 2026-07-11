from pydantic import BaseModel


class UniverseSymbol(BaseModel):
    symbol: str
    name: str
    exchange: str
    security_type: str = "stock"
    is_etf: bool = False
    price: float | None = None
    market_cap: float | None = None


class UniverseRefreshResult(BaseModel):
    downloaded: int
    accepted: int
    rejected: int
    enriched: int
