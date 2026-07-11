from datetime import UTC, datetime, timedelta

from stock_hunter.hunters.models import HunterEvent


class EventManager:
    def __init__(self, cooldown_seconds: int = 60) -> None:
        self.cooldown = timedelta(seconds=cooldown_seconds)
        self._last: dict[tuple[str, str], tuple[datetime, float]] = {}

    def accept(self, event: HunterEvent) -> bool:
        key = (event.symbol, event.event_type.value)
        previous = self._last.get(key)
        now = event.timestamp.astimezone(UTC)
        if previous and now - previous[0] < self.cooldown and event.strength <= previous[1]:
            return False
        self._last[key] = (now, event.strength)
        return True
