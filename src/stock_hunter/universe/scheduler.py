import asyncio
import logging
from datetime import UTC, datetime, timedelta

from stock_hunter.universe.service import UniverseService

logger = logging.getLogger(__name__)


def seconds_until(hour_utc: int, now: datetime | None = None) -> float:
    current = now or datetime.now(UTC)
    target = current.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
    if target <= current:
        target += timedelta(days=1)
    return (target - current).total_seconds()


async def run_daily_refresh(service: UniverseService, hour_utc: int, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=seconds_until(hour_utc))
            return
        except TimeoutError:
            pass
        try:
            result = await service.refresh()
            logger.info(
                "Universe refresh completed: downloaded=%s accepted=%s rejected=%s",
                result.downloaded,
                result.accepted,
                result.rejected,
            )
        except Exception:
            logger.exception("Scheduled universe refresh failed")
