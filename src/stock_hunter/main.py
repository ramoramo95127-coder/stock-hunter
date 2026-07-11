import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException

from stock_hunter.config import get_settings
from stock_hunter.db import create_engine, create_schema, create_session_factory, database_ready
from stock_hunter.events import EventManager
from stock_hunter.hunters.engine import HunterEngine
from stock_hunter.intraday.models import IngestResult, RvolSnapshot
from stock_hunter.intraday.service import IntradayService
from stock_hunter.logging import configure_logging
from stock_hunter.providers.factory import create_market_provider
from stock_hunter.providers.http import ProviderError
from stock_hunter.providers.models import CompanyProfile, MinuteBarData, Quote
from stock_hunter.universe.models import UniverseRefreshResult
from stock_hunter.universe.nasdaq import NasdaqUniverseSource
from stock_hunter.universe.scheduler import run_daily_refresh
from stock_hunter.universe.service import UniverseService

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = create_engine(settings.database_url)
    await create_schema(app.state.db)
    app.state.sessions = create_session_factory(app.state.db)
    app.state.intraday = IntradayService(app.state.sessions, settings)
    app.state.hunters = HunterEngine()
    app.state.event_manager = EventManager()
    app.state.redis = redis.from_url(settings.redis_url)
    app.state.provider = create_market_provider(settings)
    app.state.universe_source = NasdaqUniverseSource()
    app.state.universe = UniverseService(
        app.state.sessions,
        app.state.universe_source,
        app.state.provider,
        settings,
    )
    app.state.universe_stop = asyncio.Event()
    app.state.universe_task = asyncio.create_task(
        run_daily_refresh(
            app.state.universe,
            settings.universe_refresh_hour_utc,
            app.state.universe_stop,
        )
    )
    yield
    app.state.universe_stop.set()
    await app.state.universe_task
    await app.state.universe_source.close()
    await app.state.provider.close()
    await app.state.redis.aclose()
    await app.state.db.dispose()


app = FastAPI(title="Stock Hunter", version="0.1.0", lifespan=lifespan)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready() -> dict[str, object]:
    database = await database_ready(app.state.db)
    try:
        cache = bool(await app.state.redis.ping())
    except Exception:
        cache = False
    if not database or not cache:
        raise HTTPException(
            503, detail={"status": "degraded", "database": database, "redis": cache}
        )
    return {"status": "ready", "database": database, "redis": cache}


@app.get("/api/v1/market/quote/{symbol}", response_model=Quote)
async def quote(symbol: str) -> Quote:
    try:
        return await app.state.provider.quote(symbol)
    except ProviderError as exc:
        raise HTTPException(502, detail=str(exc)) from exc


@app.get("/api/v1/market/profile/{symbol}", response_model=CompanyProfile)
async def profile(symbol: str) -> CompanyProfile:
    try:
        return await app.state.provider.profile(symbol)
    except ProviderError as exc:
        raise HTTPException(502, detail=str(exc)) from exc


@app.post("/api/v1/universe/refresh", response_model=UniverseRefreshResult)
async def refresh_universe(enrich_limit: int = 0) -> UniverseRefreshResult:
    if enrich_limit < 0 or enrich_limit > 500:
        raise HTTPException(422, detail="enrich_limit must be between 0 and 500")
    try:
        return await app.state.universe.refresh(enrich_limit=enrich_limit)
    except Exception as exc:
        raise HTTPException(502, detail="Universe source unavailable") from exc


@app.get("/api/v1/universe")
async def list_universe(limit: int = 100, eligible_only: bool = False) -> list[dict[str, object]]:
    if limit < 1 or limit > 1000:
        raise HTTPException(422, detail="limit must be between 1 and 1000")
    stocks = await app.state.universe.list_stocks(limit=limit, eligible_only=eligible_only)
    return [
        {
            "symbol": stock.symbol,
            "name": stock.name,
            "exchange": stock.exchange,
            "price": stock.price,
            "market_cap": stock.market_cap,
            "updated_at": stock.updated_at,
        }
        for stock in stocks
    ]


@app.post("/api/v1/intraday/bars", response_model=IngestResult)
async def ingest_minute_bar(bar: MinuteBarData) -> IngestResult:
    result = await app.state.intraday.ingest(bar)
    events = [
        event
        for event in app.state.hunters.evaluate(bar, result.rvol)
        if app.state.event_manager.accept(event)
    ]
    for event in events:
        await app.state.redis.xadd(
            "stock_events",
            {
                "type": event.event_type.value,
                "symbol": event.symbol,
                "strength": str(event.strength),
                "reason": event.reason,
                "timestamp": event.timestamp.isoformat(),
            },
            maxlen=10_000,
            approximate=True,
        )
    return result


@app.get("/api/v1/intraday/rvol/{symbol}", response_model=RvolSnapshot)
async def get_rvol(symbol: str, timestamp: datetime) -> RvolSnapshot:
    return await app.state.intraday.snapshot(symbol, timestamp.astimezone(UTC))
