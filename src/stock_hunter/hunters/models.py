from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class EventType(StrEnum):
    RVOL = "rvol"
    VOLUME_ACCELERATION = "volume_acceleration"
    BREAKOUT = "breakout"
    GAP = "gap"
    MOMENTUM = "momentum"


class HunterEvent(BaseModel):
    symbol: str
    event_type: EventType
    timestamp: datetime
    strength: float
    reason: str
    data: dict[str, float | bool | str]
