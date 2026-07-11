from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from stock_hunter.hunters.models import HunterEvent


class OpportunityState(StrEnum):
    WATCHING = "watching"
    HIGH_ATTENTION = "high_attention"
    PRIME_CANDIDATE = "prime_candidate"
    WEAKENING = "weakening"
    SLEEPING = "sleeping"
    MISSED = "missed"
    REJECTED = "rejected"


class Opportunity(BaseModel):
    symbol: str
    state: OpportunityState
    score: float
    updated_at: datetime
    reasons: list[str]
    what_next: str
    invalidation: str
    events: list[HunterEvent]
    previous_state: OpportunityState | None = None
    change_reason: str | None = None
