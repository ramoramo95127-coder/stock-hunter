from datetime import datetime

from pydantic import BaseModel


class RvolSnapshot(BaseModel):
    symbol: str
    timestamp: datetime
    current_volume: int
    baseline_volume: float | None
    rvol: float | None
    baseline_days: int
    baseline_ready: bool
    accelerating: bool
    triggered: bool


class IngestResult(BaseModel):
    stored: bool
    rvol: RvolSnapshot
