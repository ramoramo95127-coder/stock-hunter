from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr

from stock_hunter.judge.models import Opportunity, OpportunityState
from stock_hunter.notifications import (
    TelegramNotifier,
    format_opportunity,
    format_test_notification,
)


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


def test_test_message_is_clearly_marked_and_contains_trade_levels() -> None:
    message = format_test_notification()
    assert "test message only" in message
    assert "Target: $10.50 (+5%)" in message
    assert "Stop: $9.70 (-3%)" in message


@pytest.mark.asyncio
async def test_send_test_posts_to_configured_chat_without_creating_a_signal() -> None:
    request_body = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_body
        request_body = request.read().decode()
        return httpx.Response(200, json={"ok": True})

    notifier = TelegramNotifier(SecretStr("test-token"), "12345")
    await notifier._client.aclose()
    notifier._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert await notifier.send_test()
    assert request_body and '"chat_id":"12345"' in request_body
    assert "test message only" in request_body
    await notifier.close()
