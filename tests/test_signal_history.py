from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from stock_hunter.db import Base
from stock_hunter.performance import TradeOutcome, open_trade
from stock_hunter.signal_history import SignalHistoryStore, StatsPeriod


@pytest.mark.asyncio
async def test_signal_history_keeps_independent_resolved_signals() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    store = SignalHistoryStore(async_sessionmaker(engine, expire_on_commit=False))
    now = datetime(2026, 7, 11, 10, tzinfo=UTC)

    first = open_trade("ABCD", 10)
    await store.start(first, None, now)
    first.outcome = TradeOutcome.STOP
    await store.update(first, now)
    second = open_trade("ABCD", 11)
    await store.start(second, None, now)

    records = await store.list()
    assert len(records) == 2
    assert {item.entry for item in records} == {10, 11}
    await engine.dispose()


@pytest.mark.asyncio
async def test_period_stats_count_target_before_stop() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    store = SignalHistoryStore(async_sessionmaker(engine, expire_on_commit=False))
    now = datetime(2026, 7, 11, 10, tzinfo=UTC)
    winner = open_trade("WIN", 10)
    await store.start(winner, None, now)
    winner.outcome = TradeOutcome.RUNNER
    await store.update(winner, now)
    loser = open_trade("LOSE", 10)
    await store.start(loser, None, now)
    loser.outcome = TradeOutcome.STOP
    await store.update(loser, now)

    stats = await store.stats(StatsPeriod.DAY, now)
    assert stats.total == 2
    assert stats.successful == 1
    assert stats.stopped == 1
    assert stats.success_rate == 50
    await engine.dispose()
