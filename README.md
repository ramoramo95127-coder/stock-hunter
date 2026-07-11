# Stock Hunter

Sprint 1 and Sprint 2 foundation: FastAPI, PostgreSQL, Redis, Docker Compose, logging,
health endpoints, provider abstraction, FMP, Finnhub, SEC, Mock, tests, and CI.

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
