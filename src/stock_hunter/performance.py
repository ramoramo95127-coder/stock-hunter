from enum import StrEnum

from pydantic import BaseModel


class TradeOutcome(StrEnum):
    OPEN = "open"
    TARGET = "target"
    STOP = "stop"
    RUNNER = "runner"


class TrackedTrade(BaseModel):
    symbol: str
    entry: float
    target: float
    stop: float
    high: float
    low: float
    outcome: TradeOutcome = TradeOutcome.OPEN
    protected_stop: float | None = None


def open_trade(symbol: str, entry: float) -> TrackedTrade:
    return TrackedTrade(
        symbol=symbol, entry=entry, target=entry * 1.05, stop=entry * 0.97, high=entry, low=entry
    )


def update_trade(trade: TrackedTrade, high: float, low: float) -> TrackedTrade:
    updated = trade.model_copy(deep=True)
    updated.high = max(updated.high, high)
    updated.low = min(updated.low, low)
    if updated.outcome == TradeOutcome.OPEN:
        if low <= updated.stop:
            updated.outcome = TradeOutcome.STOP
        elif high >= updated.target:
            updated.outcome = TradeOutcome.RUNNER
            updated.protected_stop = max(updated.entry * 1.02, updated.stop)
    elif updated.outcome == TradeOutcome.RUNNER:
        candidate = updated.high * 0.97
        updated.protected_stop = max(updated.protected_stop or updated.stop, candidate)
    return updated
