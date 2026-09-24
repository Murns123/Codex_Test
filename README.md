# JEV × EODHD Paper Trader

A long-only autonomous **paper-trading research project** for ASX and US equities.

## Architecture

EODHD → screener / quote / historical data → local indicators → JEV probabilistic evaluation → deterministic risk engine → paper broker → PostgreSQL → Next.js dashboard.

## Safety model

- Paper trading only; there is no live broker execution code.
- Long-only, no leverage.
- JEV suggests probabilities; deterministic code decides whether an order is permitted.
- Execution is disabled unless `PAPER_TRADING_ENABLED=true`.
- API keys stay in Vercel Environment Variables.

## Required environment variables

```text
EODHD_API_TOKEN
JEV_API_KEY
DATABASE_URL
CRON_SECRET
```

Optional strategy settings are documented in `.env.example`.

## Useful endpoints

- `GET /api/health`
- `GET /api/eodhd/account`
- `GET /api/market/scan?market=AU`
- `POST /api/trading/evaluate` with `{"symbol":"BHP.AU"}`
- `POST /api/trading/execute` with `{"symbol":"BHP.AU"}`
- `GET /api/portfolio`
- `GET /api/cron/asx`
- `GET /api/cron/us`

## Database

The schema self-initialises on first request when `DATABASE_URL` is present.

## Deployment

Connect this repository to Vercel, add environment variables, deploy once with
`PAPER_TRADING_ENABLED=false`, verify the endpoints, then enable paper execution.

The cron expressions are UTC and deliberately broad; the strategy should later be tightened with an exchange-calendar guard for ASX holidays, daylight-saving transitions, and US market holidays.
