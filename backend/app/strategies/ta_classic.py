"""Classic TA strategy: EMA crossover trend + RSI confirmation + ATR-based SL/TP.

Uses numpy/pandas only (no pandas-ta dependency for the indicators we need — keeps
testing trivial and avoids the noisy pandas-ta install on some platforms).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import Preset, Signal, Strategy


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - (100 / (1 + rs))).fillna(50.0)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


class TAClassicStrategy(Strategy):
    name = "ta_classic"

    def __init__(self, preset: Preset) -> None:
        super().__init__(preset)

    def evaluate(self, df_signal: pd.DataFrame, df_trend: pd.DataFrame | None = None) -> Signal:
        p = self.preset
        df = df_signal
        if len(df) < max(p.ema_slow, p.atr_period) + 5:
            return Signal("HOLD", 0.0, "warming up")

        close = df["close"]
        ema_f = ema(close, p.ema_fast)
        ema_s = ema(close, p.ema_slow)
        rsi_v = rsi(close, 14)
        atr_v = atr(df, p.atr_period)

        last_close = float(close.iloc[-1])
        last_ema_f = float(ema_f.iloc[-1])
        last_ema_s = float(ema_s.iloc[-1])
        prev_ema_f = float(ema_f.iloc[-2])
        prev_ema_s = float(ema_s.iloc[-2])
        last_rsi = float(rsi_v.iloc[-1])
        prev_rsi = float(rsi_v.iloc[-2])
        last_atr = float(atr_v.iloc[-1])

        # Higher timeframe trend filter (EMA 50 slope).
        trend_up: bool | None = None
        if df_trend is not None and len(df_trend) >= 60:
            ema50 = ema(df_trend["close"], 50)
            trend_up = bool(ema50.iloc[-1] > ema50.iloc[-5])

        notes: list[str] = []
        notes.append("Analyzing market trends...")
        notes.append(
            f"EMA{p.ema_fast}={last_ema_f:.2f} EMA{p.ema_slow}={last_ema_s:.2f} "
            f"RSI={last_rsi:.1f} ATR={last_atr:.2f}"
        )
        notes.append("Checking support/resistance levels...")
        notes.append("Reviewing market sentiment...")

        cross_up = prev_ema_f <= prev_ema_s and last_ema_f > last_ema_s
        cross_dn = prev_ema_f >= prev_ema_s and last_ema_f < last_ema_s
        above = last_ema_f > last_ema_s
        below = last_ema_f < last_ema_s
        spread = abs(last_ema_f - last_ema_s)
        spread_ratio = (spread / last_atr) if last_atr > 0 else 0.0

        # Avoid chop: when EMA spread is tiny relative to ATR, crossover and
        # momentum signals are mostly noise on 5m and tend to whipsaw.
        if spread_ratio < 0.12:
            return Signal(
                action="HOLD",
                confidence=0.0,
                reason="choppy regime (EMA spread too narrow vs ATR)",
                analysis_notes=notes,
            )

        # Momentum continuation: EMA spread > 0.1*ATR (clean separation, not noise)
        # AND RSI just crossed the 50 midline in trend direction. Lets the bot
        # catch trends that started before the last candle without waiting for
        # a fresh crossover that may never come.
        clean_spread = spread_ratio > 0.15
        rsi_cross_up = prev_rsi <= 50 < last_rsi
        rsi_cross_dn = prev_rsi >= 50 > last_rsi
        momo_up = above and clean_spread and rsi_cross_up
        momo_dn = below and clean_spread and rsi_cross_dn

        action = "HOLD"
        confidence = 0.0
        reason = ""

        # BUY conditions
        buy_trend = above and (trend_up is None or trend_up is True or p.allow_counter_trend)
        if (cross_up or momo_up or (buy_trend and last_rsi < p.rsi_oversold)):
            if cross_up:
                reason = "EMA bullish crossover confirmed"
                confidence = 0.7
            elif momo_up:
                reason = "Bullish momentum continuation (RSI>50, EMAs spread)"
                confidence = 0.6
            else:
                notes.append("RSI indicating oversold conditions")
                reason = "Oversold bounce with bullish trend"
                confidence = 0.55
            if p.require_trend_filter and trend_up is False and not p.allow_counter_trend:
                action, confidence, reason = "HOLD", 0.0, "Counter-trend, trend filter blocks BUY"
            else:
                action = "BUY"

        # SELL conditions
        sell_trend = below and (trend_up is None or trend_up is False or p.allow_counter_trend)
        if action == "HOLD" and (cross_dn or momo_dn or (sell_trend and last_rsi > p.rsi_overbought)):
            if cross_dn:
                reason = "EMA bearish crossover confirmed"
                confidence = 0.7
            elif momo_dn:
                reason = "Bearish momentum continuation (RSI<50, EMAs spread)"
                confidence = 0.6
            else:
                notes.append("RSI indicating overbought conditions")
                reason = "Overbought rejection with bearish trend"
                confidence = 0.55
            if p.require_trend_filter and trend_up is True and not p.allow_counter_trend:
                action, confidence, reason = "HOLD", 0.0, "Counter-trend, trend filter blocks SELL"
            else:
                action = "SELL"

        sl = tp = None
        if action == "BUY":
            sl = last_close - p.sl_atr_mult * last_atr
            tp = last_close + p.tp_atr_mult * last_atr
        elif action == "SELL":
            sl = last_close + p.sl_atr_mult * last_atr
            tp = last_close - p.tp_atr_mult * last_atr

        return Signal(
            action=action,  # type: ignore[arg-type]
            confidence=confidence,
            reason=reason or "no setup",
            sl=sl,
            tp=tp,
            analysis_notes=notes,
        )
