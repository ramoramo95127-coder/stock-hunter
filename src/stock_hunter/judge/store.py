from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from stock_hunter.db import DecisionRecord, OpportunityRecord
from stock_hunter.judge.models import Opportunity


class OpportunityStore:
    def __init__(self, sessions: async_sessionmaker) -> None:
        self.sessions = sessions

    async def save(self, opportunity: Opportunity) -> None:
        values = {
            "symbol": opportunity.symbol,
            "state": opportunity.state.value,
            "score": opportunity.score,
            "reasons": opportunity.reasons,
            "what_next": opportunity.what_next,
            "invalidation": opportunity.invalidation,
            "updated_at": opportunity.updated_at,
        }
        statement = insert(OpportunityRecord).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[OpportunityRecord.symbol],
            set_={key: getattr(statement.excluded, key) for key in values if key != "symbol"},
        )
        decision = DecisionRecord(
            symbol=opportunity.symbol,
            state=opportunity.state.value,
            previous_state=opportunity.previous_state.value if opportunity.previous_state else None,
            score=opportunity.score,
            reason=opportunity.change_reason or "Opportunity evaluated",
            evidence=[event.model_dump(mode="json") for event in opportunity.events],
            created_at=opportunity.updated_at,
        )
        async with self.sessions() as session:
            await session.execute(statement)
            session.add(decision)
            await session.commit()

    async def timeline(self, symbol: str, limit: int = 100) -> list[DecisionRecord]:
        query = (
            select(DecisionRecord)
            .where(DecisionRecord.symbol == symbol.upper())
            .order_by(DecisionRecord.created_at.desc())
            .limit(limit)
        )
        async with self.sessions() as session:
            return list((await session.scalars(query)).all())
