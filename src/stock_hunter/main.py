import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
import redis.asyncio as redis
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from stock_hunter.config import get_settings
from stock_hunter.dashboard import dashboard
from stock_hunter.db import create_engine, create_schema, create_session_factory, database_ready
from stock_hunter.events import EventManager
from stock_hunter.hunters.engine import HunterEngine
from stock_hunter.intraday.models import IngestResult, RvolSnapshot
from stock_hunter.intraday.service import IntradayService
from stock_hunter.judge.engine import Judge
from stock_hunter.judge.models import Opportunity
from stock_hunter.judge.store import OpportunityStore
from stock_hunter.live import FinnhubLiveCollector
from stock_hunter.logging import configure_logging
from stock_hunter.notifications import TelegramNotifier
from stock_hunter.opportunity_cards import OpportunityCard, build_card
from stock_hunter.performance import PerformanceEngine
from stock_hunter.performance_store import PerformanceStore
from stock_hunter.providers.factory import create_market_provider
from stock_hunter.providers.http import ProviderError
from stock_hunter.providers.models import CompanyProfile, MinuteBarData, Quote
from stock_hunter.radar import FmpRadar, run_radar
from stock_hunter.signal_history import SignalHistoryStore, SignalStats, StatsPeriod
from stock_hunter.universe.models import UniverseRefreshResult
from stock_hunter.universe.nasdaq import NasdaqUniverseSource
from stock_hunter.universe.scheduler import run_daily_refresh
from stock_hunter.universe.service import UniverseService

settings = get_settings()
configure_logging(settings.log_level)


class ManualEntry(BaseModel):
    symbol: str
    entry: float = Field(gt=0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = create_engine(settings.database_url)
    await create_schema(app.state.db)
    app.state.sessions = create_session_factory(app.state.db)
    app.state.intraday = IntradayService(app.state.sessions, settings)
    app.state.hunters = HunterEngine()
    app.state.event_manager = EventManager()
    app.state.judge = Judge()
    app.state.opportunity_store = OpportunityStore(app.state.sessions)
    restored_opportunities = await app.state.opportunity_store.restore()
    app.state.judge.restore(restored_opportunities)
    for expired in app.state.judge.expire(datetime.now(UTC)):
        await app.state.opportunity_store.save(expired)
    app.state.telegram = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    app.state.performance = PerformanceEngine()
    app.state.performance_store = PerformanceStore(app.state.sessions)
    app.state.signal_history = SignalHistoryStore(app.state.sessions)
    await app.state.performance_store.restore(app.state.performance)
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
    app.state.live_stop = asyncio.Event()
    app.state.live_task = None
    app.state.radar = None
    app.state.radar_task = None
    if settings.live_stream_enabled and settings.finnhub_api_key:
        collector = FinnhubLiveCollector(
            settings.finnhub_api_key,
            settings.live_symbol_list,
            lambda bar: process_bar(app, bar),
        )
        app.state.live_task = asyncio.create_task(collector.run(app.state.live_stop))
        if settings.radar_enabled and settings.fmp_api_key:
            app.state.radar = FmpRadar(
                settings.fmp_api_key,
                settings.universe_min_price,
                settings.universe_max_price,
                settings.radar_max_symbols,
            )
            app.state.radar_task = asyncio.create_task(
                run_radar(
                    app.state.radar,
                    collector,
                    settings.live_symbol_list,
                    settings.radar_refresh_seconds,
                    app.state.live_stop,
                )
            )
    yield
    app.state.live_stop.set()
    if app.state.live_task:
        await app.state.live_task
    if app.state.radar_task:
        await app.state.radar_task
    if app.state.radar:
        await app.state.radar.close()
    app.state.universe_stop.set()
    await app.state.universe_task
    await app.state.universe_source.close()
    await app.state.telegram.close()
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
    return await process_bar(app, bar)


async def process_bar(application: FastAPI, bar: MinuteBarData) -> IngestResult:
    updated_trade = application.state.performance.update(bar.symbol.upper(), bar.high, bar.low)
    if updated_trade:
        await application.state.performance_store.save(updated_trade)
        await application.state.signal_history.update(updated_trade, bar.timestamp)
    result = await application.state.intraday.ingest(bar)
    events = [
        event
        for event in application.state.hunters.evaluate(bar, result.rvol)
        if application.state.event_manager.accept(event)
    ]
    if events:
        opportunity = application.state.judge.consider(events, bar.timestamp)
        if opportunity:
            await application.state.opportunity_store.save(opportunity)
            await application.state.telegram.notify(opportunity)
            if opportunity.state.value == "prime_candidate":
                trade = application.state.performance.start(opportunity.symbol, bar.close)
                await application.state.performance_store.save(trade)
                await application.state.signal_history.start(trade, opportunity, bar.timestamp)
    for event in events:
        await application.state.redis.xadd(
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


@app.get("/api/v1/opportunities", response_model=list[Opportunity])
async def top_opportunities(limit: int = 5) -> list[Opportunity]:
    if limit < 1 or limit > 5:
        raise HTTPException(422, detail="limit must be between 1 and 5")
    await expire_opportunities(app)
    return app.state.judge.top(limit)


@app.get("/api/v1/opportunity-cards", response_model=list[OpportunityCard])
async def opportunity_cards(limit: int = 5) -> list[OpportunityCard]:
    if limit < 1 or limit > 5:
        raise HTTPException(422, detail="limit must be between 1 and 5")
    await expire_opportunities(app)
    opportunities = app.state.judge.top(limit)
    return [
        build_card(item, rank, app.state.performance.trades.get(item.symbol))
        for rank, item in enumerate(opportunities, start=1)
    ]


async def expire_opportunities(application: FastAPI) -> None:
    for opportunity in application.state.judge.expire(datetime.now(UTC)):
        await application.state.opportunity_store.save(opportunity)


@app.get("/api/v1/opportunities/{symbol}/timeline")
async def opportunity_timeline(symbol: str, limit: int = 100) -> list[dict[str, object]]:
    if limit < 1 or limit > 500:
        raise HTTPException(422, detail="limit must be between 1 and 500")
    records = await app.state.opportunity_store.timeline(symbol, limit)
    return [
        {
            "state": item.state,
            "previous_state": item.previous_state,
            "score": item.score,
            "reason": item.reason,
            "evidence": item.evidence,
            "created_at": item.created_at,
        }
        for item in records
    ]


@app.post("/api/v1/notifications/telegram/test")
async def test_telegram_notification() -> dict[str, object]:
    if not app.state.telegram.enabled:
        raise HTTPException(
            503,
            detail=("Telegram is not configured; set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID"),
        )
    try:
        sent = await app.state.telegram.send_test()
    except httpx.HTTPError as exc:
        raise HTTPException(502, detail="Telegram test message could not be sent") from exc
    return {
        "status": "sent" if sent else "not_sent",
        "test_only": True,
        "signal_created": False,
        "trade_created": False,
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard_page() -> HTMLResponse:
    return dashboard()


@app.get("/api/v1/performance")
async def performance_summary() -> dict[str, object]:
    periods = [StatsPeriod.DAY, StatsPeriod.WEEK, StatsPeriod.MONTH, StatsPeriod.ALL]
    summaries = await asyncio.gather(
        *(app.state.signal_history.stats(period) for period in periods)
    )
    return {item.period.value: item.model_dump(mode="json") for item in summaries}


@app.get("/api/v1/performance/{period}", response_model=SignalStats)
async def performance_by_period(period: StatsPeriod) -> SignalStats:
    return await app.state.signal_history.stats(period)


@app.get("/api/v1/signals")
async def signal_history(limit: int = 100) -> list[dict[str, object]]:
    if limit < 1 or limit > 500:
        raise HTTPException(422, detail="limit must be between 1 and 500")
    records = await app.state.signal_history.list(limit)
    return [
        {
            "id": item.id,
            "symbol": item.symbol,
            "source": item.source,
            "state": item.state,
            "entry": item.entry,
            "target": item.target,
            "stop": item.stop,
            "high": item.high,
            "low": item.low,
            "outcome": item.outcome,
            "catalyst": item.catalyst,
            "reasons": item.reasons,
            "opened_at": item.opened_at,
            "resolved_at": item.resolved_at,
        }
        for item in records
    ]


@app.get("/api/v1/trades")
async def trades() -> list[dict[str, object]]:
    return [trade.model_dump(mode="json") for trade in app.state.performance.trades.values()]


@app.post("/api/v1/trades/manual")
async def manual_entry(request: ManualEntry) -> dict[str, object]:
    trade = app.state.performance.enter_manual(request.symbol, request.entry)
    await app.state.performance_store.save(trade)
    await app.state.signal_history.start(trade, None, datetime.now(UTC))
    return trade.model_dump(mode="json")


@app.get("/api/v1/intraday/rvol/{symbol}", response_model=RvolSnapshot)
async def get_rvol(symbol: str, timestamp: datetime) -> RvolSnapshot:
    return await app.state.intraday.snapshot(symbol, timestamp.astimezone(UTC))
