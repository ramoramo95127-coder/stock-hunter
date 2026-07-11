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


class MinuteBarData(BaseModel):
    symbol: str
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int = Field(ge=0)
    source: str
    previous_close: float | None = Field(default=None, gt=0)
    resistance: float | None = Field(default=None, gt=0)
