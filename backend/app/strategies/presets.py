"""Built-in strategy presets."""
from __future__ import annotations

from .base import Preset

PRESETS: dict[str, Preset] = {
    "conservative": Preset(
        name="conservative",
        rsi_oversold=20, rsi_overbought=80,
        ema_fast=9, ema_slow=34,
        atr_period=14, sl_atr_mult=2.0, tp_atr_mult=4.0,
        max_trades_per_day=2, require_trend_filter=True, allow_counter_trend=False,
    ),
    "balanced": Preset(
        name="balanced",
        rsi_oversold=30, rsi_overbought=70,
        ema_fast=9, ema_slow=21,
        atr_period=14, sl_atr_mult=1.5, tp_atr_mult=2.5,
        max_trades_per_day=4, require_trend_filter=True, allow_counter_trend=False,
    ),
    "aggressive": Preset(
        name="aggressive",
        rsi_oversold=40, rsi_overbought=60,
        ema_fast=5, ema_slow=13,
        atr_period=10, sl_atr_mult=1.2, tp_atr_mult=2.0,
        max_trades_per_day=12, require_trend_filter=True, allow_counter_trend=False,
        chop_threshold=0.07, momo_spread_threshold=0.10,
    ),
}


def get_preset(name: str) -> Preset:
    if name not in PRESETS:
        raise ValueError(f"Unknown preset: {name}")
    return PRESETS[name]
