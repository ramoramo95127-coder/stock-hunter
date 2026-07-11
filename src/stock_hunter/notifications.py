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
        response = await self._client.post(
            f"https://api.telegram.org/bot{self.token.get_secret_value()}/sendMessage",
            json={"chat_id": self.chat_id, "text": format_opportunity(opportunity)},
        )
        response.raise_for_status()
        return True

    async def close(self) -> None:
        await self._client.aclose()
