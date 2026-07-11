from sqlalchemy import desc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from stock_hunter.db import DecisionRecord, OpportunityRecord
from stock_hunter.hunters.models import HunterEvent
from stock_hunter.judge.models import Opportunity, OpportunityState


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

    async def restore(self) -> list[Opportunity]:
        async with self.sessions() as session:
            records = list((await session.scalars(select(OpportunityRecord))).all())
            if not records:
                return []
            decisions = list(
                (
                    await session.scalars(
                        select(DecisionRecord)
                        .where(DecisionRecord.symbol.in_([item.symbol for item in records]))
                        .order_by(desc(DecisionRecord.created_at))
                    )
                ).all()
            )
        latest_evidence: dict[str, list] = {}
        for decision in decisions:
            latest_evidence.setdefault(decision.symbol, decision.evidence)
        return [
            Opportunity(
                symbol=record.symbol,
                state=OpportunityState(record.state),
                score=record.score,
                updated_at=record.updated_at,
                reasons=record.reasons,
                what_next=record.what_next,
                invalidation=record.invalidation,
                events=[
                    HunterEvent.model_validate(event)
                    for event in latest_evidence.get(record.symbol, [])
                ],
            )
            for record in records
        ]
