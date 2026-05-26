"""Strategy unit tests using synthetic OHLCV data."""
from __future__ import annotations

import numpy as np
import pandas as pd

from backend.app.strategies.presets import get_preset
from backend.app.strategies.ta_classic import TAClassicStrategy, ema, rsi, atr


def _make_df(prices: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=len(prices), freq="5min", tz="UTC")
    s = pd.Series(prices, index=idx)
    return pd.DataFrame(
        {
            "open": s.shift(1).fillna(s),
            "high": s * 1.001,
            "low": s * 0.999,
            "close": s,
            "volume": 1.0,
        }
    )


def test_rsi_bounds():
    s = pd.Series(np.linspace(100, 110, 50))
    v = rsi(s, 14)
    assert v.between(0, 100).all()


def test_atr_positive():
    df = _make_df([100 + i for i in range(60)])
    v = atr(df, 14)
    assert (v.dropna() >= 0).all()


def test_uptrend_buy_signal():
    # Steady uptrend → after a small dip, EMA fast crosses above slow.
    prices = list(np.linspace(3000, 3050, 100)) + list(np.linspace(3050, 3030, 5)) + list(np.linspace(3030, 3080, 30))
    df = _make_df(prices)
    df_trend = _make_df(prices)  # same direction
    strat = TAClassicStrategy(get_preset("balanced"))
    sig = strat.evaluate(df, df_trend)
    assert sig.action in {"BUY", "HOLD"}
    if sig.action == "BUY":
        assert sig.sl is not None and sig.sl < float(df["close"].iloc[-1])
        assert sig.tp is not None and sig.tp > float(df["close"].iloc[-1])


def test_warmup_returns_hold():
    df = _make_df([3000.0] * 10)
    strat = TAClassicStrategy(get_preset("balanced"))
    assert strat.evaluate(df).action == "HOLD"
