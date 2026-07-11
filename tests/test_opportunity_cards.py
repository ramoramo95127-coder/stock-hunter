from datetime import UTC, datetime

from stock_hunter.hunters.models import EventType, HunterEvent
from stock_hunter.judge.models import Opportunity, OpportunityState
from stock_hunter.opportunity_cards import build_card


def test_card_explains_trade_and_calculates_levels() -> None:
    event = HunterEvent(
        symbol="ABCD",
        event_type=EventType.BREAKOUT,
        timestamp=datetime.now(UTC),
        strength=0.9,
        reason="Price broke resistance",
        data={"price": 10.0},
    )
    opportunity = Opportunity(
        symbol="ABCD",
        state=OpportunityState.HIGH_ATTENTION,
        score=72,
        updated_at=event.timestamp,
        reasons=[event.reason],
        what_next="Wait for continuation",
        invalidation="Failed breakout",
        events=[event],
    )

    card = build_card(opportunity, 1, None)

    assert card.catalyst == "breakout"
    assert card.entry_low == 9.95
    assert card.entry_high == 10.05
    assert card.target == 10.5
    assert card.stop == 9.7
    assert "not a guaranteed prediction" in card.explanation
