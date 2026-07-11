import httpx
from pydantic import SecretStr

from stock_hunter.judge.models import Opportunity, OpportunityState


def format_opportunity(opportunity: Opportunity) -> str:
    reasons = "\n".join(f"• {reason}" for reason in opportunity.reasons[:3])
    return (
        f"{opportunity.symbol} — {opportunity.state.value}\n"
        f"Why now:\n{reasons}\n\n"
        f"What next: {opportunity.what_next}\n"
        f"Invalidation: {opportunity.invalidation}"
    )


def format_test_notification() -> str:
    return (
        "🧪 Stock Hunter — Telegram test\n\n"
        "TEST — prime_candidate\n"
        "Confidence: 72.50\n"
        "Why now:\n"
        "• RVOL reached 3.20\n"
        "• Price broke resistance with accelerating volume\n\n"
        "Entry zone: $9.95–$10.05\n"
        "Target: $10.50 (+5%)\n"
        "Stop: $9.70 (-3%)\n\n"
        "What next: Watch for continuation without chasing\n"
        "Invalidation: Loss of volume or failed breakout\n\n"
        "This is a test message only. No signal or trade was created."
    )


class TelegramNotifier:
    def __init__(self, token: SecretStr | None, chat_id: str | None) -> None:
        self.token = token
        self.chat_id = chat_id
        self._client = httpx.AsyncClient(timeout=10)

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    async def notify(self, opportunity: Opportunity) -> bool:
        important = opportunity.state in {
            OpportunityState.HIGH_ATTENTION,
            OpportunityState.PRIME_CANDIDATE,
            OpportunityState.WEAKENING,
            OpportunityState.MISSED,
        }
        changed = opportunity.previous_state != opportunity.state
        if not self.enabled or not important or not changed:
            return False
        await self._send(format_opportunity(opportunity))
        return True

    async def send_test(self) -> bool:
        if not self.enabled:
            return False
        await self._send(format_test_notification())
        return True

    async def _send(self, text: str) -> None:
        response = await self._client.post(
            f"https://api.telegram.org/bot{self.token.get_secret_value()}/sendMessage",
            json={"chat_id": self.chat_id, "text": text},
        )
        response.raise_for_status()

    async def close(self) -> None:
        await self._client.aclose()
