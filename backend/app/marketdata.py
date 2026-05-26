"""Market data: REST backfill + periodic refresh of OHLCV frames per timeframe.

We use polling rather than a raw websocket for v1 — Binance closed candles arrive
predictably and this keeps the dependency surface small. The engine ticks once per
closed signal candle.
"""
from __future__ import annotations

import asyncio
from typing import Dict

import pandas as pd

from . import logs
from .exchange import Exchange

OHLCV_COLS = ["ts", "open", "high", "low", "close", "volume"]


class MarketData:
    def __init__(self, exchange: Exchange) -> None:
        self.exchange = exchange
        self.frames: Dict[str, pd.DataFrame] = {}

    def _to_df(self, raw: list[list[float]]) -> pd.DataFrame:
        df = pd.DataFrame(raw, columns=OHLCV_COLS)
        df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
        df = df.set_index("ts")
        return df.astype({c: "float64" for c in ("open", "high", "low", "close", "volume")})

    def backfill(self, timeframe: str, limit: int = 500) -> pd.DataFrame:
        # Retry with backoff — first call after startup often races a Binance hiccup.
        import time as _time
        backoffs = (0, 2, 5, 10, 20)
        last_err: Exception | None = None
        for attempt, delay in enumerate(backoffs, start=1):
            if delay:
                _time.sleep(delay)
            try:
                raw = self.exchange.fetch_ohlcv(timeframe, limit=limit)
                df = self._to_df(raw)
                self.frames[timeframe] = df
                if attempt > 1:
                    logs.info(f"Backfill [{timeframe}] recovered on attempt {attempt}")
                return df
            except Exception as e:  # noqa: BLE001
                last_err = e
                logs.info(
                    f"Backfill [{timeframe}] attempt {attempt}/{len(backoffs)} failed: "
                    f"{type(e).__name__}: {e!r}"
                )
        raise RuntimeError(
            f"backfill [{timeframe}] failed after {len(backoffs)} attempts: "
            f"{type(last_err).__name__}: {last_err!r}"
        )

    def refresh(self, timeframe: str, limit: int = 200) -> pd.DataFrame:
        # Retry with exponential backoff to ride out transient Binance hiccups.
        backoffs = (0, 2, 5, 10)
        last_err: Exception | None = None
        import time as _time
        for attempt, delay in enumerate(backoffs, start=1):
            if delay:
                _time.sleep(delay)
            try:
                raw = self.exchange.fetch_ohlcv(timeframe, limit=limit)
                new = self._to_df(raw)
                prev = self.frames.get(timeframe)
                if prev is None:
                    self.frames[timeframe] = new
                else:
                    merged = pd.concat([prev, new])
                    merged = merged[~merged.index.duplicated(keep="last")].sort_index()
                    # cap memory
                    self.frames[timeframe] = merged.tail(2000)
                if attempt > 1:
                    logs.info(f"OHLCV [{timeframe}] recovered on attempt {attempt}")
                return self.frames[timeframe]
            except Exception as e:  # noqa: BLE001
                last_err = e
                logs.info(
                    f"OHLCV [{timeframe}] attempt {attempt}/{len(backoffs)} failed: "
                    f"{type(e).__name__}: {e!r}"
                )
        logs.error(
            f"OHLCV refresh failed [{timeframe}] after {len(backoffs)} attempts: "
            f"{type(last_err).__name__}: {last_err!r}"
        )
        return self.frames.get(timeframe, pd.DataFrame(columns=OHLCV_COLS))

    async def wait_for_next_close(self, timeframe: str) -> None:
        """Sleep until just after the next candle close for the given timeframe."""
        seconds = _timeframe_seconds(timeframe)
        loop = asyncio.get_running_loop()
        now = loop.time()
        # align to wall clock instead — use monotonic offset from current minute boundary.
        import time
        wall = time.time()
        next_close = (int(wall // seconds) + 1) * seconds + 2  # +2s grace for exchange
        await asyncio.sleep(max(0.5, next_close - wall))


def _timeframe_seconds(tf: str) -> int:
    units = {"m": 60, "h": 3600, "d": 86400}
    return int(tf[:-1]) * units[tf[-1]]
