from datetime import UTC, datetime, timedelta

from stock_hunter.events import EventManager
from stock_hunter.hunters.engine import HunterEngine
from stock_hunter.hunters.models import EventType
from stock_hunter.intraday.models import RvolSnapshot
from stock_hunter.providers.models import MinuteBarData


def bar(**changes) -> MinuteBarData:
    values = dict(
        symbol="ABCD",
        timestamp=datetime(2026, 7, 11, 13, 31, tzinfo=UTC),
        open=10,
        high=10.6,
        low=9.9,
        close=10.5,
        volume=500_000,
        source="test",
        previous_close=9.5,
        resistance=10.25,
    )
    values.update(changes)
    return MinuteBarData(**values)


def snapshot(**changes) -> RvolSnapshot:
    values = dict(
        symbol="ABCD",
        timestamp=datetime(2026, 7, 11, 13, 31, tzinfo=UTC),
        current_volume=500_000,
        baseline_volume=100_000,
        rvol=5,
        baseline_days=20,
        baseline_ready=True,
        accelerating=True,
        triggered=True,
    )
    values.update(changes)
    return RvolSnapshot(**values)


def test_independent_hunters_emit_multiple_evidence_events() -> None:
    kinds = {event.event_type for event in HunterEngine().evaluate(bar(), snapshot())}
    assert {
        EventType.RVOL,
        EventType.VOLUME_ACCELERATION,
        EventType.BREAKOUT,
        EventType.GAP,
        EventType.MOMENTUM,
    }.issubset(kinds)


def test_breakout_requires_price_above_resistance() -> None:
    events = HunterEngine().evaluate(bar(close=10.1), snapshot(triggered=False, accelerating=False))
    assert EventType.BREAKOUT not in {event.event_type for event in events}


def test_event_manager_suppresses_weaker_duplicate_but_accepts_improvement() -> None:
    manager = EventManager()
    event = HunterEngine().evaluate(bar(), snapshot(rvol=2.0))[0]
    assert manager.accept(event)
    assert not manager.accept(event)
    stronger = event.model_copy(
        update={"strength": 1.0, "timestamp": event.timestamp + timedelta(seconds=10)}
    )
    assert manager.accept(stronger)
