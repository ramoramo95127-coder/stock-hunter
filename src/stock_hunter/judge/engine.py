from datetime import datetime, timedelta

from stock_hunter.hunters.models import EventType, HunterEvent
from stock_hunter.judge.models import Opportunity, OpportunityState

WEIGHTS = {
    EventType.RVOL: 0.28,
    EventType.VOLUME_ACCELERATION: 0.22,
    EventType.BREAKOUT: 0.24,
    EventType.GAP: 0.10,
    EventType.MOMENTUM: 0.16,
}


class Judge:
    def __init__(self, evidence_ttl_minutes: int = 15) -> None:
        self.ttl = timedelta(minutes=evidence_ttl_minutes)
        self._events: dict[str, dict[EventType, HunterEvent]] = {}
        self._opportunities: dict[str, Opportunity] = {}

    def consider(
        self, events: list[HunterEvent], now: datetime | None = None
    ) -> Opportunity | None:
        if not events:
            return None
        current = now or max(event.timestamp for event in events)
        symbol = events[0].symbol
        evidence = self._events.setdefault(symbol, {})
        for event in events:
            existing = evidence.get(event.event_type)
            if existing is None or event.timestamp >= existing.timestamp:
                evidence[event.event_type] = event
        active = [event for event in evidence.values() if current - event.timestamp <= self.ttl]
        previous = self._opportunities.get(symbol)
        opportunity = self._judge(symbol, active, current, previous)
        self._opportunities[symbol] = opportunity
        return opportunity

    def _judge(
        self, symbol: str, events: list[HunterEvent], now: datetime, previous: Opportunity | None
    ) -> Opportunity:
        score = round(sum(WEIGHTS[event.event_type] * event.strength for event in events) * 100, 2)
        types = {event.event_type for event in events}
        if not events:
            state = OpportunityState.SLEEPING
        elif score >= 55 and len(types) >= 3:
            state = OpportunityState.PRIME_CANDIDATE
        elif score >= 32 or len(types) >= 2:
            state = OpportunityState.HIGH_ATTENTION
        else:
            state = OpportunityState.WATCHING
        reasons = [
            event.reason for event in sorted(events, key=lambda item: item.strength, reverse=True)
        ]
        what_next, invalidation = self._guidance(types, state)
        previous_state = previous.state if previous else None
        change_reason = None
        if previous_state and previous_state != state:
            direction = "raised" if score >= previous.score else "lowered"
            change_reason = (
                f"State {direction}: active evidence changed "
                f"from {previous.score:.2f} to {score:.2f}"
            )
        return Opportunity(
            symbol=symbol,
            state=state,
            score=score,
            updated_at=now,
            reasons=reasons,
            what_next=what_next,
            invalidation=invalidation,
            events=events,
            previous_state=previous_state,
            change_reason=change_reason,
        )

    @staticmethod
    def _guidance(types: set[EventType], state: OpportunityState) -> tuple[str, str]:
        if state == OpportunityState.PRIME_CANDIDATE:
            return (
                "Watch for continuation without chasing an extended candle",
                "Loss of volume or failed breakout",
            )
        if EventType.BREAKOUT not in types:
            return (
                "Wait for a clean breakout while volume remains active",
                "Volume fades before price confirms",
            )
        if EventType.RVOL not in types:
            return (
                "Wait for stronger relative volume confirmation",
                "Price falls back below resistance",
            )
        return "Monitor for one more confirming event", "Momentum and volume weaken together"

    def top(self, limit: int = 5) -> list[Opportunity]:
        active = [
            item
            for item in self._opportunities.values()
            if item.state not in {OpportunityState.REJECTED, OpportunityState.MISSED}
        ]
        return sorted(active, key=lambda item: (item.score, item.updated_at), reverse=True)[:limit]
