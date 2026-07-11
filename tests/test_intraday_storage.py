from datetime import UTC, datetime

from stock_hunter.providers.models import MinuteBarData


def test_analysis_context_is_not_part_of_minute_bar_storage() -> None:
    bar = MinuteBarData(
        symbol="TEST",
        timestamp=datetime.now(UTC),
        open=10,
        high=11,
        low=9,
        close=10.5,
        volume=1000,
        source="test",
        previous_close=9.5,
        resistance=10.25,
    )
    stored = bar.model_dump(exclude={"previous_close", "resistance"})
    assert "previous_close" not in stored
    assert "resistance" not in stored
