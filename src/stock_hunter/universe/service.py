from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from stock_hunter.config import Settings
from stock_hunter.db import Stock
from stock_hunter.providers.base import MarketDataProvider
from stock_hunter.providers.http import ProviderError
from stock_hunter.universe.models import UniverseRefreshResult, UniverseSymbol
from stock_hunter.universe.nasdaq import NasdaqUniverseSource, is_common_stock


class UniverseService:
    def __init__(
        self,
        sessions: async_sessionmaker,
        source: NasdaqUniverseSource,
        market: MarketDataProvider,
        settings: Settings,
    ) -> None:
        self.sessions = sessions
        self.source = source
        self.market = market
        self.settings = settings

    async def refresh(self, *, enrich_limit: int = 0) -> UniverseRefreshResult:
        downloaded = await self.source.fetch()
        accepted = [item for item in downloaded if is_common_stock(item)]
        enriched = 0
        for item in accepted[:enrich_limit]:
            if await self._enrich(item):
                enriched += 1
        await self._store(accepted)
        return UniverseRefreshResult(
            downloaded=len(downloaded),
            accepted=len(accepted),
            rejected=len(downloaded) - len(accepted),
            enriched=enriched,
        )

    async def _enrich(self, item: UniverseSymbol) -> bool:
        try:
            quote = await self.market.quote(item.symbol)
            profile = await self.market.profile(item.symbol)
        except ProviderError:
            return False
        item.price = quote.price
        item.market_cap = profile.market_cap
        return True

    async def _store(self, items: list[UniverseSymbol]) -> None:
        now = datetime.now(UTC)
        values = [
            {
                "symbol": item.symbol,
                "name": item.name,
                "exchange": item.exchange,
                "security_type": item.security_type,
                "is_etf": item.is_etf,
                "is_active": True,
                "price": item.price,
                "market_cap": item.market_cap,
                "updated_at": now,
            }
            for item in items
        ]
        async with self.sessions() as session:
            if values:
                statement = insert(Stock).values(values)
                statement = statement.on_conflict_do_update(
                    index_elements=[Stock.symbol],
                    set_={
                        "name": statement.excluded.name,
                        "exchange": statement.excluded.exchange,
                        "is_active": True,
                        "price": statement.excluded.price,
                        "market_cap": statement.excluded.market_cap,
                        "updated_at": now,
                    },
                )
                await session.execute(statement)
            await session.commit()

    async def list_stocks(self, *, limit: int = 100, eligible_only: bool = False) -> list[Stock]:
        query = select(Stock).where(Stock.is_active.is_(True)).order_by(Stock.symbol).limit(limit)
        if eligible_only:
            query = query.where(
                Stock.price.between(
                    self.settings.universe_min_price, self.settings.universe_max_price
                ),
                Stock.market_cap.between(
                    self.settings.universe_min_market_cap, self.settings.universe_max_market_cap
                ),
            )
        async with self.sessions() as session:
            return list((await session.scalars(query)).all())
