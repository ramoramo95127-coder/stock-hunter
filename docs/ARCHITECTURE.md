# Architecture

Stock Hunter uses ports and adapters so market logic never depends on one vendor.

The FastAPI service exposes health and normalized market endpoints. PostgreSQL stores
durable data; Redis stores ephemeral state and will carry event streams. The Market
Gateway provides contracts with Mock, FMP, Finnhub, and SEC adapters. Future Hunter
and Judge modules consume only provider contracts, never vendor implementations.

Credentials load exclusively from environment variables as secret values and are not
included in provider errors or logs.

## Universe Engine

The Universe Engine downloads official Nasdaq Trader listed-symbol files, normalizes
exchange codes, removes ETFs and non-common securities, and performs idempotent
PostgreSQL upserts. Vendor enrichment is optional and bounded to protect API quotas.
Eligibility is a separate query over known price and market-cap fields; unknown values
remain explicit rather than being estimated.

## Intraday Collector

Minute bars are idempotently stored by symbol and UTC minute. RVOL uses the same clock
minute across prior sessions, avoiding the distortion of comparing the open with an
all-day average. A minimum-session threshold prevents immature baselines from becoming
signals. RVOL triggers and three-minute volume acceleration publish normalized events
to Redis Streams; future Hunters consume those events without depending on storage or
vendor code.
