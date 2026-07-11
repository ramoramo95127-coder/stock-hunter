from pydantic import BaseModel

from stock_hunter.judge.models import Opportunity
from stock_hunter.performance import TrackedTrade


class OpportunityCard(BaseModel):
    rank: int
    symbol: str
    state: str
    confidence: float
    current_price: float | None
    entry_low: float | None
    entry_high: float | None
    target: float | None
    stop: float | None
    catalyst: str
    explanation: str
    reasons: list[str]
    what_next: str
    invalidation: str
    risk_note: str
    trade_source: str | None


def build_card(
    opportunity: Opportunity,
    rank: int,
    trade: TrackedTrade | None,
) -> OpportunityCard:
    event = max(opportunity.events, key=lambda item: item.strength) if opportunity.events else None
    event_price = event.data.get("price") if event else None
    price = trade.entry if trade else float(event_price) if event_price is not None else None
    entry_low = round(price * 0.995, 4) if price else None
    entry_high = round(price * 1.005, 4) if price else None
    target = trade.target if trade else round(price * 1.05, 4) if price else None
    stop = trade.stop if trade else round(price * 0.97, 4) if price else None
    catalyst = event.event_type.value if event else "activity_under_review"
    lead = opportunity.reasons[0] if opportunity.reasons else "Unusual activity detected"
    explanation = (
        f"{opportunity.symbol} is ranked #{rank} because {lead.lower()}. "
        f"The evidence currently supports {opportunity.state.value.replace('_', ' ')}; "
        "this is a monitored scenario, not a guaranteed prediction."
    )
    return OpportunityCard(
        rank=rank,
        symbol=opportunity.symbol,
        state=opportunity.state.value,
        confidence=opportunity.score,
        current_price=price,
        entry_low=entry_low,
        entry_high=entry_high,
        target=target,
        stop=stop,
        catalyst=catalyst,
        explanation=explanation,
        reasons=opportunity.reasons,
        what_next=opportunity.what_next,
        invalidation=opportunity.invalidation,
        risk_note=(
            "Do not chase outside the entry zone; the setup is invalid if "
            f"{opportunity.invalidation.lower()}."
        ),
        trade_source=("manual" if trade.manual else "paper") if trade else None,
    )
