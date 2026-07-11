from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from stock_hunter.db import TradeRecord
from stock_hunter.performance import PerformanceEngine, TrackedTrade, TradeOutcome


class PerformanceStore:
    def __init__(self, sessions: async_sessionmaker) -> None:
        self.sessions = sessions

    async def save(self, trade: TrackedTrade) -> None:
        values = {
            **trade.model_dump(mode="json"),
            "outcome": trade.outcome.value,
            "updated_at": datetime.now(UTC),
        }
        statement = insert(TradeRecord).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[TradeRecord.symbol],
            set_={key: getattr(statement.excluded, key) for key in values if key != "symbol"},
        )
        async with self.sessions() as session:
            await session.execute(statement)
            await session.commit()

    async def restore(self, engine: PerformanceEngine) -> int:
        async with self.sessions() as session:
            rows = list((await session.scalars(select(TradeRecord))).all())
        for row in rows:
            engine.trades[row.symbol] = TrackedTrade(
                symbol=row.symbol,
                entry=row.entry,
                target=row.target,
                stop=row.stop,
                high=row.high,
                low=row.low,
                outcome=TradeOutcome(row.outcome),
                protected_stop=row.protected_stop,
                manual=row.manual,
            )
        return len(rows)
