from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from stock_hunter.db import SignalRecord
from stock_hunter.judge.models import Opportunity
from stock_hunter.performance import TrackedTrade, TradeOutcome


class StatsPeriod(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    ALL = "all"


class SignalStats(BaseModel):
    period: StatsPeriod
    total: int
    successful: int
    stopped: int
    open: int
    success_rate: float
    paper: int
    manual: int


class SignalHistoryStore:
    def __init__(self, sessions: async_sessionmaker) -> None:
        self.sessions = sessions

    async def start(
        self,
        trade: TrackedTrade,
        opportunity: Opportunity | None,
        now: datetime,
    ) -> SignalRecord:
        source = "manual" if trade.manual else "paper"
        async with self.sessions() as session:
            existing = await session.scalar(
                select(SignalRecord)
                .where(
                    SignalRecord.symbol == trade.symbol,
                    SignalRecord.source == source,
                    SignalRecord.outcome == TradeOutcome.OPEN.value,
                )
                .order_by(desc(SignalRecord.opened_at))
                .limit(1)
            )
            if existing:
                return existing
            event = (
                max(opportunity.events, key=lambda item: item.strength)
                if opportunity and opportunity.events
                else None
            )
            record = SignalRecord(
                id=str(uuid4()),
                symbol=trade.symbol,
                source=source,
                state=opportunity.state.value if opportunity else "manual_entry",
                entry=trade.entry,
                target=trade.target,
                stop=trade.stop,
                high=trade.high,
                low=trade.low,
                outcome=trade.outcome.value,
                catalyst=event.event_type.value if event else "manual",
                reasons=opportunity.reasons if opportunity else ["Manual entry recorded by user"],
                opened_at=now,
                resolved_at=None,
                updated_at=now,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def update(self, trade: TrackedTrade, now: datetime) -> None:
        source = "manual" if trade.manual else "paper"
        async with self.sessions() as session:
            record = await session.scalar(
                select(SignalRecord)
                .where(
                    SignalRecord.symbol == trade.symbol,
                    SignalRecord.source == source,
                    SignalRecord.resolved_at.is_(None),
                )
                .order_by(desc(SignalRecord.opened_at))
                .limit(1)
            )
            if not record:
                return
            record.high = trade.high
            record.low = trade.low
            record.outcome = trade.outcome.value
            record.updated_at = now
            if trade.outcome in {TradeOutcome.RUNNER, TradeOutcome.STOP, TradeOutcome.TARGET}:
                record.resolved_at = now
            await session.commit()

    async def list(self, limit: int = 100) -> list[SignalRecord]:
        async with self.sessions() as session:
            return list(
                (
                    await session.scalars(
                        select(SignalRecord).order_by(desc(SignalRecord.opened_at)).limit(limit)
                    )
                ).all()
            )

    async def stats(self, period: StatsPeriod, now: datetime | None = None) -> SignalStats:
        current = now or datetime.now(UTC)
        start = self._period_start(period, current)
        statement = select(SignalRecord)
        if start:
            statement = statement.where(SignalRecord.opened_at >= start)
        async with self.sessions() as session:
            records = list((await session.scalars(statement)).all())
        successful = sum(
            item.outcome in {TradeOutcome.RUNNER.value, TradeOutcome.TARGET.value}
            for item in records
        )
        stopped = sum(item.outcome == TradeOutcome.STOP.value for item in records)
        open_count = len(records) - successful - stopped
        resolved = successful + stopped
        return SignalStats(
            period=period,
            total=len(records),
            successful=successful,
            stopped=stopped,
            open=open_count,
            success_rate=round(successful / resolved * 100, 2) if resolved else 0,
            paper=sum(item.source == "paper" for item in records),
            manual=sum(item.source == "manual" for item in records),
        )

    @staticmethod
    def _period_start(period: StatsPeriod, now: datetime) -> datetime | None:
        if period == StatsPeriod.DAY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == StatsPeriod.WEEK:
            day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return day - timedelta(days=day.weekday())
        if period == StatsPeriod.MONTH:
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return None
