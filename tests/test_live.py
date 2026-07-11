from stock_hunter.live import MinuteAggregator


def test_aggregator_builds_and_rolls_minute_bar() -> None:
    aggregator = MinuteAggregator()
    assert aggregator.add_trade("abcd", 10, 100, 1_700_000_000_000) is None
    assert aggregator.add_trade("abcd", 11, 50, 1_700_000_020_000) is None
    completed = aggregator.add_trade("abcd", 12, 25, 1_700_000_080_000)
    assert completed
    assert completed.open == 10
    assert completed.high == 11
    assert completed.close == 11
    assert completed.volume == 150
