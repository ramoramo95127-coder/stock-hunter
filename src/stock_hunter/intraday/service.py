from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, extract, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from stock_hunter.config import Settings
from stock_hunter.db import MinuteBar
from stock_hunter.intraday.models import IngestResult, RvolSnapshot
from stock_hunter.intraday.rvol import calculate_rvol, is_accelerating
from stock_hunter.providers.models import MinuteBarData


class IntradayService:
    def __init__(self, sessions: async_sessionmaker, settings: Settings) -> None:
        self.sessions = sessions
        self.settings = settings

    async def ingest(self, bar: MinuteBarData) -> IngestResult:
        normalized = bar.model_copy(
            update={
                "symbol": bar.symbol.upper(),
                "timestamp": bar.timestamp.astimezone(UTC).replace(second=0, microsecond=0),
            }
        )
        stored = await self._store(normalized)
        snapshot = await self.snapshot(normalized.symbol, normalized.timestamp)
        return IngestResult(stored=stored, rvol=snapshot)

    async def _store(self, bar: MinuteBarData) -> bool:
        stored_values = bar.model_dump(exclude={"previous_close", "resistance"})
        statement = insert(MinuteBar).values(**stored_values)
        statement = statement.on_conflict_do_update(
            constraint="uq_minute_bar_symbol_timestamp",
            set_={
                "open": statement.excluded.open,
                "high": statement.excluded.high,
                "low": statement.excluded.low,
                "close": statement.excluded.close,
                "volume": statement.excluded.volume,
                "source": statement.excluded.source,
            },
        )
        async with self.sessions() as session:
            await session.execute(statement)
            await session.commit()
        return True

    async def snapshot(self, symbol: str, timestamp: datetime) -> RvolSnapshot:
        current, history, recent = await self._volumes(symbol.upper(), timestamp)
        baseline, rvol = calculate_rvol(current, history)
        days = len(history)
        ready = days >= self.settings.rvol_minimum_days
        accelerating = is_accelerating(recent)
        return RvolSnapshot(
            symbol=symbol.upper(),
            timestamp=timestamp,
            current_volume=current,
            baseline_volume=baseline,
            rvol=rvol if ready else None,
            baseline_days=days,
            baseline_ready=ready,
            accelerating=accelerating,
            triggered=bool(ready and rvol is not None and rvol >= self.settings.rvol_trigger),
        )

    async def _volumes(self, symbol: str, timestamp: datetime) -> tuple[int, list[int], list[int]]:
        start = timestamp - timedelta(days=self.settings.rvol_baseline_days + 10)
        minute_conditions = and_(
            extract("hour", MinuteBar.timestamp) == timestamp.hour,
            extract("minute", MinuteBar.timestamp) == timestamp.minute,
        )
        async with self.sessions() as session:
            current_query = select(MinuteBar.volume).where(
                MinuteBar.symbol == symbol, MinuteBar.timestamp == timestamp
            )
            current = (await session.scalar(current_query)) or 0
            history_query = (
                select(MinuteBar.volume)
                .where(
                    MinuteBar.symbol == symbol,
                    MinuteBar.timestamp >= start,
                    MinuteBar.timestamp < timestamp.replace(hour=0, minute=0),
                    minute_conditions,
                )
                .order_by(MinuteBar.timestamp.desc())
                .limit(self.settings.rvol_baseline_days)
            )
            history = list((await session.scalars(history_query)).all())
            recent_query = (
                select(MinuteBar.volume)
                .where(
                    MinuteBar.symbol == symbol,
                    MinuteBar.timestamp <= timestamp,
                    MinuteBar.timestamp >= timestamp - timedelta(minutes=2),
                )
                .order_by(MinuteBar.timestamp)
            )
            recent = list((await session.scalars(recent_query)).all())
        return current, history, recent
