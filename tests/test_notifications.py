from datetime import UTC, datetime

from stock_hunter.judge.models import Opportunity, OpportunityState
from stock_hunter.notifications import TelegramNotifier, format_opportunity


def opportunity() -> Opportunity:
    return Opportunity(
        symbol="ABCD",
        state=OpportunityState.PRIME_CANDIDATE,
        score=70,
        updated_at=datetime.now(UTC),
        reasons=["RVOL confirmed"],
        what_next="Watch continuation",
        invalidation="Failed breakout",
        events=[],
        previous_state=OpportunityState.WATCHING,
    )


def test_message_contains_decision_guidance() -> None:
    message = format_opportunity(opportunity())
    assert "Why now" in message and "What next" in message and "Invalidation" in message


def test_notifier_is_disabled_without_secrets() -> None:
    assert not TelegramNotifier(None, None).enabled
