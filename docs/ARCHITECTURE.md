# Architecture

Stock Hunter uses ports and adapters so market logic never depends on one vendor.

The FastAPI service exposes health and normalized market endpoints. PostgreSQL stores
durable data; Redis stores ephemeral state and will carry event streams. The Market
Gateway provides contracts with Mock, FMP, Finnhub, and SEC adapters. Future Hunter
and Judge modules consume only provider contracts, never vendor implementations.

Credentials load exclusively from environment variables as secret values and are not
included in provider errors or logs.
