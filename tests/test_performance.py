from stock_hunter.performance import PerformanceEngine, TradeOutcome, open_trade, update_trade


def test_target_before_stop_enters_runner_and_protects_profit() -> None:
    trade = update_trade(open_trade("ABCD", 10), high=10.6, low=9.9)
    assert trade.outcome == TradeOutcome.RUNNER
    assert trade.protected_stop == 10.2


def test_stop_is_recorded() -> None:
    trade = update_trade(open_trade("ABCD", 10), high=10.1, low=9.6)
    assert trade.outcome == TradeOutcome.STOP


def test_runner_stop_never_moves_backwards() -> None:
    trade = update_trade(open_trade("ABCD", 10), high=10.6, low=10)
    raised = update_trade(trade, high=11, low=10.4)
    lower_high = update_trade(raised, high=10.8, low=10.5)
    assert lower_high.protected_stop == raised.protected_stop


def test_performance_engine_does_not_duplicate_open_trade() -> None:
    engine = PerformanceEngine()
    first = engine.start("ABCD", 10)
    second = engine.start("ABCD", 11)
    assert first.entry == second.entry == 10
