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
    manual: bool = False


def open_trade(symbol: str, entry: float, manual: bool = False) -> TrackedTrade:
    return TrackedTrade(
        symbol=symbol,
        entry=entry,
        target=round(entry * 1.05, 4),
        stop=round(entry * 0.97, 4),
        high=entry,
        low=entry,
        manual=manual,
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


class PerformanceEngine:
    def __init__(self) -> None:
        self.trades: dict[str, TrackedTrade] = {}

    def start(self, symbol: str, entry: float) -> TrackedTrade:
        trade = self.trades.get(symbol)
        if trade and trade.outcome in {TradeOutcome.OPEN, TradeOutcome.RUNNER}:
            return trade
        trade = open_trade(symbol, entry)
        self.trades[symbol] = trade
        return trade

    def update(self, symbol: str, high: float, low: float) -> TrackedTrade | None:
        trade = self.trades.get(symbol)
        if not trade:
            return None
        updated = update_trade(trade, high, low)
        self.trades[symbol] = updated
        return updated

    def enter_manual(self, symbol: str, entry: float) -> TrackedTrade:
        trade = open_trade(symbol.upper(), entry, manual=True)
        self.trades[trade.symbol] = trade
        return trade

    def summary(self) -> dict[str, int | float]:
        closed = [trade for trade in self.trades.values() if trade.outcome == TradeOutcome.STOP]
        runners = [trade for trade in self.trades.values() if trade.outcome == TradeOutcome.RUNNER]
        total = len(self.trades)
        return {
            "total": total,
            "stops": len(closed),
            "runners": len(runners),
            "target_rate": round(len(runners) / total * 100, 2) if total else 0.0,
        }
