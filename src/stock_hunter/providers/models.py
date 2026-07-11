from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Quote(BaseModel):
    symbol: str
    price: float = Field(gt=0)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str


class CompanyProfile(BaseModel):
    symbol: str
    name: str
    exchange: str | None = None
    market_cap: float | None = None
    source: str


class NewsItem(BaseModel):
    id: str
    headline: str
    url: str
    published_at: datetime
    symbols: list[str] = []
    source: str


class Filing(BaseModel):
    accession_number: str
    form: str
    filed_at: datetime
    url: str
    source: str = "sec"
