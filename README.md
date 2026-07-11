# Stock Hunter

Sprint 1 and Sprint 2 foundation: FastAPI, PostgreSQL, Redis, Docker Compose, logging,
health endpoints, provider abstraction, FMP, Finnhub, SEC, Mock, tests, and CI.

Sprint 3 adds the official Nasdaq Trader symbol universe, security-type cleanup,
PostgreSQL persistence, configurable price/market-cap eligibility, optional provider
enrichment, and universe APIs.

Sprint 4 adds durable minute bars, same-minute historical RVOL baselines, baseline
quality reporting, volume acceleration, and Redis events for future Hunters.

Sprint 6–7 add explainable opportunity states, top-5 ranking, durable current
opportunities, and an append-only decision timeline in PostgreSQL.

## Start

1. Copy .env.example to .env.
2. Run: docker compose up --build -d
3. Open: http://localhost:8000/health/live
4. Check dependencies: http://localhost:8000/health/ready

The default Mock provider requires no key. To use FMP set DEFAULT_PROVIDER=fmp and
FMP_API_KEY in .env. For Finnhub use DEFAULT_PROVIDER=finnhub and FINNHUB_API_KEY.
Use a truthful contact email in SEC_USER_AGENT. Never commit or paste credentials.

## QA

Create a Python 3.12 environment, install with pip install -e ".[dev]", then run:

- ruff check .
- ruff format --check .
- pytest -q
- docker compose config

See docs/ARCHITECTURE.md.

## Universe

- `POST /api/v1/universe/refresh` downloads and stores the official symbol lists.
- `POST /api/v1/universe/refresh?enrich_limit=100` also enriches up to 100 symbols.
- `GET /api/v1/universe?limit=100` lists active common stocks.
- `GET /api/v1/universe?eligible_only=true` requires known price and market cap within
  the configured range. Missing vendor data is never invented.

## Intraday and RVOL

- `POST /api/v1/intraday/bars` stores or updates a normalized minute bar.
- `GET /api/v1/intraday/rvol/{symbol}?timestamp=...` returns an RVOL snapshot.
- RVOL compares the current minute with the same minute across prior sessions.
- Until `RVOL_MINIMUM_DAYS` exist, `baseline_ready` is false and `rvol` remains null.
- Triggered or accelerating observations are published to the Redis `stock_events` stream.

## Opportunities

- `GET /api/v1/opportunities?limit=5` returns the current ranked opportunities.
- `GET /api/v1/opportunities/{symbol}/timeline` explains every persisted decision.
