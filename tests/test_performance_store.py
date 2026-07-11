from stock_hunter.performance import PerformanceEngine


def test_restored_trade_container_accepts_existing_trade() -> None:
    engine = PerformanceEngine()
    trade = engine.start("ABCD", 10)
    engine.trades[trade.symbol] = trade
    assert engine.start("ABCD", 12).entry == 10
