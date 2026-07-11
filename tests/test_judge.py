from datetime import UTC, datetime, timedelta

from stock_hunter.hunters.models import EventType, HunterEvent
from stock_hunter.judge.engine import Judge
from stock_hunter.judge.models import OpportunityState

NOW = datetime(2026, 7, 11, 13, 30, tzinfo=UTC)


def event(kind: EventType, strength: float = 0.8, symbol: str = "ABCD") -> HunterEvent:
    return HunterEvent(
        symbol=symbol,
        event_type=kind,
        timestamp=NOW,
        strength=strength,
        reason=f"{kind.value} confirmed",
        data={},
    )


def test_single_strong_event_starts_watching_without_blocking_detection() -> None:
    result = Judge().consider([event(EventType.RVOL, 1.0)])
    assert result and result.state == OpportunityState.WATCHING


def test_multiple_evidence_promotes_prime_candidate() -> None:
    result = Judge().consider(
        [
            event(EventType.RVOL, 1),
            event(EventType.BREAKOUT, 1),
            event(EventType.VOLUME_ACCELERATION, 1),
            event(EventType.MOMENTUM, 1),
        ]
    )
    assert result and result.state == OpportunityState.PRIME_CANDIDATE


def test_top_returns_only_requested_best_opportunities() -> None:
    judge = Judge()
    judge.consider([event(EventType.RVOL, 0.5, "LOW")])
    judge.consider([event(EventType.RVOL, 1, "HIGH"), event(EventType.BREAKOUT, 1, "HIGH")])
    assert [item.symbol for item in judge.top(1)] == ["HIGH"]


def test_state_change_is_explained() -> None:
    judge = Judge()
    judge.consider([event(EventType.RVOL, 1)])
    result = judge.consider([event(EventType.BREAKOUT, 1), event(EventType.MOMENTUM, 1)])
    assert result and result.previous_state == OpportunityState.WATCHING
    assert result.change_reason


def test_expired_evidence_moves_opportunity_to_sleeping() -> None:
    judge = Judge(evidence_ttl_minutes=15)
    judge.consider([event(EventType.RVOL, 1)])
    changed = judge.expire(NOW + timedelta(minutes=16))
    assert len(changed) == 1
    assert changed[0].state == OpportunityState.SLEEPING
    assert judge.top() == []


def test_partial_evidence_loss_marks_strong_opportunity_as_weakening() -> None:
    judge = Judge(evidence_ttl_minutes=15)
    old = NOW - timedelta(minutes=14)
    old_events = [
        event(EventType.RVOL, 1),
        event(EventType.BREAKOUT, 1),
        event(EventType.VOLUME_ACCELERATION, 1),
        event(EventType.MOMENTUM, 1),
    ]
    for item in old_events:
        item.timestamp = old
    judge.consider(old_events, old)
    fresh = event(EventType.RVOL, 1)
    fresh.timestamp = NOW
    judge.consider([fresh], NOW)
    changed = judge.expire(NOW + timedelta(minutes=2))
    assert len(changed) == 1
    assert changed[0].state == OpportunityState.WEAKENING


def test_restored_opportunity_keeps_evidence_for_expiration() -> None:
    original = Judge().consider([event(EventType.RVOL, 1)])
    assert original
    judge = Judge()
    assert judge.restore([original]) == 1
    assert judge.top(1)[0].symbol == "ABCD"
    assert judge.expire(NOW + timedelta(minutes=16))[0].state == OpportunityState.SLEEPING
