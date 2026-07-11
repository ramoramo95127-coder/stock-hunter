from datetime import UTC, datetime

from stock_hunter.universe.scheduler import seconds_until


def test_seconds_until_same_day() -> None:
    now = datetime(2026, 7, 11, 10, 30, tzinfo=UTC)
    assert seconds_until(12, now) == 90 * 60


def test_seconds_until_next_day() -> None:
    now = datetime(2026, 7, 11, 13, 0, tzinfo=UTC)
    assert seconds_until(12, now) == 23 * 60 * 60
