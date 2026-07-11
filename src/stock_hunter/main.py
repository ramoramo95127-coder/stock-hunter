from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException

from stock_hunter.config import get_settings
from stock_hunter.db import create_engine, database_ready
from stock_hunter.logging import configure_logging
from stock_hunter.providers.factory import create_market_provider
from stock_hunter.providers.http import ProviderError
from stock_hunter.providers.models import CompanyProfile, Quote

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = create_engine(settings.database_url)
    app.state.redis = redis.from_url(settings.redis_url)
    app.state.provider = create_market_provider(settings)
    yield
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
