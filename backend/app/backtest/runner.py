"""Simple bar-by-bar backtest reusing the live Strategy.evaluate function.

Uses ccxt to pull historical OHLCV (paginated). No vectorbt dependency here so the
backtest works out of the box; vectorbt is optional and only used for richer reports.
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from typing import Iterable

import ccxt
import pandas as pd

from ..settings import get_settings
from ..strategies.presets import get_preset
from ..strategies.ta_classic import TAClassicStrategy

OHLCV_COLS = ["ts", "open", "high", "low", "close", "volume"]


def fetch_ohlcv_paginated(
    symbol: str, timeframe: str, since_ms: int, until_ms: int
) -> pd.DataFrame:
    client = ccxt.binanceusdm({"enableRateLimit": True, "options": {"defaultType": "future"}})
    out: list[list[float]] = []
    cursor = since_ms
    while cursor < until_ms:
        batch = client.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=1500)
        if not batch:
            break
        out.extend(batch)
        cursor = batch[-1][0] + 1
        if len(batch) < 2:
            break
        time.sleep(client.rateLimit / 1000)
    df = pd.DataFrame(out, columns=OHLCV_COLS).drop_duplicates(subset=["ts"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    return df.set_index("ts").astype({c: "float64" for c in ("open", "high", "low", "close", "volume")})


def simulate(
    df_sig: pd.DataFrame,
    df_trend: pd.DataFrame,
    strategy_name: str,
    starting_equity: float = 10_000.0,
    risk_pct: float = 0.005,
    fee_bps: float = 4.0,  # 0.04% taker
) -> dict:
    preset = get_preset(strategy_name)
    strat = TAClassicStrategy(preset)

    equity = starting_equity
    peak = equity
    max_dd = 0.0
    trades: list[dict] = []
    open_trade: dict | None = None
    fee = fee_bps / 10_000.0

    # Iterate bars; for each bar, use closed candle data up to and including current.
    for i in range(60, len(df_sig)):
        window = df_sig.iloc[: i + 1]
        # align trend to bar's timestamp
        ts = window.index[-1]
        trend_win = df_trend[df_trend.index <= ts]

        # Handle open trade exit on this bar (intra-bar high/low vs SL/TP).
        if open_trade is not None:
            bar = df_sig.iloc[i]
            hit_sl = bar["low"] <= open_trade["sl"] if open_trade["side"] == "BUY" else bar["high"] >= open_trade["sl"]
            hit_tp = bar["high"] >= open_trade["tp"] if open_trade["side"] == "BUY" else bar["low"] <= open_trade["tp"]
            exit_price: float | None = None
            if hit_sl and hit_tp:
                exit_price = open_trade["sl"]  # assume SL hit first (conservative)
            elif hit_sl:
                exit_price = open_trade["sl"]
            elif hit_tp:
                exit_price = open_trade["tp"]
            if exit_price is not None:
                direction = 1 if open_trade["side"] == "BUY" else -1
                pnl = (exit_price - open_trade["entry"]) * direction * open_trade["qty"]
                pnl -= (open_trade["entry"] + exit_price) * open_trade["qty"] * fee
                equity += pnl
                open_trade.update(exit=exit_price, pnl=pnl, exit_ts=ts)
                trades.append(open_trade)
                open_trade = None
                peak = max(peak, equity)
                dd = (equity - peak) / peak if peak > 0 else 0
                max_dd = min(max_dd, dd)

        if open_trade is not None:
            continue

        signal = strat.evaluate(window, trend_win)
        if signal.action == "HOLD" or signal.sl is None:
            continue
        entry = float(window["close"].iloc[-1])
        stop_dist = abs(entry - signal.sl)
        if stop_dist <= 0:
            continue
        qty = (equity * risk_pct) / stop_dist
        open_trade = {
            "ts": ts, "side": signal.action, "entry": entry,
            "sl": signal.sl, "tp": signal.tp, "qty": qty, "reason": signal.reason,
        }

    closed = trades
    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] <= 0]
    total_pnl = sum(t["pnl"] for t in closed)
    win_rate = (len(wins) / len(closed) * 100) if closed else 0
    profit_factor = (sum(t["pnl"] for t in wins) / abs(sum(t["pnl"] for t in losses))) if losses and sum(t["pnl"] for t in losses) != 0 else float("inf") if wins else 0
    return {
        "strategy": strategy_name,
        "trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "inf",
        "total_pnl": round(total_pnl, 2),
        "end_equity": round(equity, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
    }


def main(argv: Iterable[str] | None = None) -> None:
    s = get_settings()
    p = argparse.ArgumentParser(description="XAUUSDT strategy backtest")
    p.add_argument("--strategy", default="balanced", choices=["conservative", "balanced", "aggressive"])
    p.add_argument("--symbol", default=s.symbol)
    p.add_argument("--from", dest="from_", default="2024-06-01")
    p.add_argument("--to", dest="to_", default=datetime.utcnow().strftime("%Y-%m-%d"))
    p.add_argument("--equity", type=float, default=10_000.0)
    p.add_argument("--risk", type=float, default=s.risk_pct)
    args = p.parse_args(list(argv) if argv else None)

    since = int(datetime.fromisoformat(args.from_).replace(tzinfo=timezone.utc).timestamp() * 1000)
    until = int(datetime.fromisoformat(args.to_).replace(tzinfo=timezone.utc).timestamp() * 1000)
    print(f"Downloading {args.symbol} {s.signal_timeframe} from {args.from_} to {args.to_} …")
    df_sig = fetch_ohlcv_paginated(args.symbol, s.signal_timeframe, since, until)
    print(f"  signal bars: {len(df_sig)}")
    df_trend = fetch_ohlcv_paginated(args.symbol, s.trend_timeframe, since, until)
    print(f"  trend  bars: {len(df_trend)}")

    report = simulate(df_sig, df_trend, args.strategy, args.equity, args.risk)
    print("\n=== Backtest report ===")
    for k, v in report.items():
        print(f"{k:>18}: {v}")


if __name__ == "__main__":
    main()
