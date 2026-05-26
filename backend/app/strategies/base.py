"""Strategy ABC and Signal type."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal, Optional

import pandas as pd

Action = Literal["BUY", "SELL", "HOLD"]


@dataclass
class Signal:
    action: Action
    confidence: float = 0.0  # 0..1
    reason: str = ""
    sl: Optional[float] = None
    tp: Optional[float] = None
    analysis_notes: list[str] = field(default_factory=list)


@dataclass
class Preset:
    name: str
    rsi_oversold: float = 30
    rsi_overbought: float = 70
    ema_fast: int = 9
    ema_slow: int = 21
    atr_period: int = 14
    sl_atr_mult: float = 1.5
    tp_atr_mult: float = 2.5
    max_trades_per_day: int = 8
    require_trend_filter: bool = True   # use higher timeframe trend
    allow_counter_trend: bool = False


class Strategy(ABC):
    name: str = "abstract"

    def __init__(self, preset: Preset) -> None:
        self.preset = preset

    @abstractmethod
    def evaluate(self, df_signal: pd.DataFrame, df_trend: pd.DataFrame | None = None) -> Signal:
        """Return a Signal given the most recent closed candle data."""
