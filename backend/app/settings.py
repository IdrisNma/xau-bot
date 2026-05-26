"""Application settings loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Binance
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True

    # Trading
    symbol: str = "XAU/USDT:USDT"
    leverage: int = 3
    margin_mode: Literal["isolated", "cross"] = "isolated"
    signal_timeframe: str = "5m"
    trend_timeframe: str = "1h"
    default_strategy: str = "balanced"

    # Risk
    risk_pct: float = 0.005
    daily_max_loss_pct: float = 0.03
    max_trades_per_day: int = 8
    cooldown_seconds_after_sl: int = 600

    # Safety
    live_enabled: bool = False

    # API
    api_bearer_token: str = "change-me-please"
    cors_origins: str = "http://localhost:3000"

    # Storage
    database_url: str = "sqlite:///./xau_bot.db"
    log_retention: int = 2000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
