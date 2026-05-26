# XAU Bot — Intelligent Gold (XAUUSDT) Trading Bot for Binance USDT-M Futures

A full-stack algorithmic trading bot for the **XAU/USDT perpetual** contract on Binance USDT-M Futures, with a Horizon-style web dashboard for live stats, recent trades, and color-coded streaming logs.

> ⚠️ **Trading risk.** This software trades real money when configured to do so. Use Binance **testnet** until you have validated the strategy on your own account. Live trading is gated behind a second `LIVE_ENABLED=true` env flag in addition to your API credentials.

---

## Stack

- **Backend**: Python 3.11 · FastAPI · ccxt (`binanceusdm`) · pandas · SQLModel (SQLite) · loguru
- **Frontend**: Next.js 14 · TypeScript · Tailwind · lucide-react
- **Backtesting**: bar-by-bar simulator reusing the live `Strategy.evaluate` (vectorbt optional)
- **Dev**: Docker Compose · Makefile · pytest · ruff

## Layout

```
backend/app/
  main.py            FastAPI bootstrap
  api.py             REST + WebSocket
  engine.py          Trading loop (start/stop/delete, tick → signal → risk → order)
  exchange.py        ccxt binanceusdm wrapper (testnet-aware, live-gated)
  marketdata.py      OHLCV backfill + scheduled refresh
  risk.py            Position sizing + daily/cooldown circuit breakers
  logs.py            Loguru sink → DB + in-memory pub/sub for WS
  db.py              SQLModel models + engine
  strategies/        base, presets (conservative/balanced/aggressive), ta_classic
  backtest/runner.py CLI backtester
backend/tests/       pytest suites
frontend/            Next.js dashboard (mirrors the Horizon screenshots)
```

## Setup

```bash
cp .env.example .env             # fill in BINANCE_API_KEY / SECRET (testnet keys to start)
make install                     # python + npm deps
make api                         # backend on :8000
make web                         # frontend on :3100 (separate terminal)
```

Or with Docker:

```bash
docker compose up --build
```

## Workflow (staged rollout)

1. **Backtest** historical XAUUSDT data:
   ```bash
   python -m backend.app.backtest.runner --strategy balanced --from 2024-06-01 --to 2025-06-01
   ```
2. **Testnet** (default): `BINANCE_TESTNET=true`. Start the bot from the dashboard or:
   ```bash
   curl -X POST http://localhost:8000/bot/start \
     -H "Authorization: Bearer $API_BEARER_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"strategy":"balanced"}'
   ```
3. **Live** (only when you're ready): in `.env` set `BINANCE_TESTNET=false`, `LIVE_ENABLED=true`,
   use **production** API keys with **Futures trading enabled** and **IP whitelist**. Start with the
   `conservative` preset and small `RISK_PCT` (e.g. 0.0025).

## Strategies

- `conservative` — EMA 9/34 + RSI 20/80, 2× ATR SL / 4× ATR TP, max 2 trades/day, trend filter on.
- `balanced` (default) — EMA 9/21 + RSI 30/70, 1.5× / 2.5× ATR, max 4 trades/day, trend filter on.
- `aggressive` — EMA 5/13 + RSI 35/65, 1.0× / 1.5× ATR, max 8 trades/day, counter-trend allowed.

All strategies use a higher-timeframe (1h) EMA-50 slope as the trend filter and ATR-derived bracket
orders (reduce-only stop-market + take-profit-market) for risk control.

## Risk controls

- Position size = `(equity × leverage × RISK_PCT) / stop_distance`, rounded to the symbol's qty step.
- **Daily max loss** auto-pauses the engine and records `paused_reason`.
- **Max trades/day** cap.
- **Cooldown after SL** suppresses new entries for `COOLDOWN_SECONDS_AFTER_SL` seconds.
- `live_enabled=false` short-circuits all real order placement even with valid keys.

## API

| Method | Path           | Auth | Description                          |
| ------ | -------------- | ---- | ------------------------------------ |
| GET    | `/bot`         | —    | Current bot config & strategies list |
| POST   | `/bot/start`   | ✅   | Start engine `{ "strategy": "…" }`   |
| POST   | `/bot/stop`    | ✅   | Stop + flatten any open position     |
| DELETE | `/bot`         | ✅   | Stop + wipe trade/log/equity history |
| GET    | `/stats`       | —    | Trades, win-rate %, profit, last trade |
| GET    | `/trades`      | —    | Recent trades                        |
| GET    | `/logs`        | —    | Recent logs (in-memory ring buffer)  |
| GET    | `/equity`      | —    | Equity points over time              |
| WS     | `/ws?token=…`  | ✅   | Live log stream                      |

## Tests

```bash
pytest -q
```

## Roadmap (not in v1)

- Multi-symbol portfolio · trailing stops · S/R-breakout strategy module
- LLM/news sentiment ingestion · multi-user auth · mobile app
- vectorbt-powered backtest report with equity curve PNG
