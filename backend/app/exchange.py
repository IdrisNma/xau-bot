"""Bitget USDT-M Futures adapter (ccxt). Testnet-aware. Paper-mode fallback.

Modes (auto-detected):
- **paper**: no API credentials → orders simulated locally using public data.
- **testnet**: ``BITGET_TESTNET=true`` with valid testnet keys → Bitget sandbox.
- **live**: ``BITGET_TESTNET=false`` AND ``LIVE_ENABLED=true`` AND valid keys.
  Otherwise order placement is short-circuited.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

import ccxt

from . import logs
from .settings import get_settings


_PAPER_STATE_FILE = Path("paper_state.json")


def _retry(fn, *, attempts: int = 3, backoff: float = 1.5):
    """Retry a callable on transient ccxt network errors."""
    last_exc = None
    for i in range(attempts):
        try:
            return fn()
        except (ccxt.RequestTimeout, ccxt.NetworkError, ccxt.ExchangeNotAvailable) as e:
            last_exc = e
            if i < attempts - 1:
                time.sleep(backoff ** i)
    raise last_exc  # type: ignore[misc]


class Exchange:
    def __init__(self) -> None:
        s = get_settings()
        self.settings = s
        self.symbol = s.symbol
        self.paper = not (s.bitget_api_key and s.bitget_api_secret and s.bitget_passphrase)
        self.client = ccxt.bitget(
            {
                "apiKey": s.bitget_api_key,
                "secret": s.bitget_api_secret,
                "password": s.bitget_passphrase,
                "enableRateLimit": True,
                "timeout": 30000,
                "options": {"defaultType": "swap"},
            }
        )
        if s.bitget_testnet and not self.paper:
            self.client.set_sandbox_mode(True)

        # Paper-mode local state
        self._paper_balance = 100.0
        self._paper_position: Optional[dict[str, Any]] = None
        self._paper_sl: Optional[float] = None
        self._paper_tp: Optional[float] = None
        self._load_paper_state()

        if self.paper:
            logs.info(
                f"Running in PAPER mode (no API keys). Balance=${self._paper_balance:.2f}. "
                "Orders are simulated locally."
            )
        else:
            mode = "TESTNET" if s.bitget_testnet else "LIVE"
            logs.info(f"Exchange: Bitget USDT-M Futures [{mode}]")

    # ---- paper persistence ---------------------------------------------
    def _load_paper_state(self) -> None:
        if not _PAPER_STATE_FILE.exists():
            return
        try:
            data = json.loads(_PAPER_STATE_FILE.read_text())
            self._paper_balance = float(data.get("balance", self._paper_balance))
            self._paper_position = data.get("position")
            self._paper_sl = data.get("sl")
            self._paper_tp = data.get("tp")
        except Exception as e:  # noqa: BLE001
            logs.error(f"failed to load paper state: {e}")

    def _save_paper_state(self) -> None:
        try:
            _PAPER_STATE_FILE.write_text(json.dumps({
                "balance": self._paper_balance,
                "position": self._paper_position,
                "sl": self._paper_sl,
                "tp": self._paper_tp,
            }))
        except Exception as e:  # noqa: BLE001
            logs.error(f"failed to save paper state: {e}")

    # ---- setup ----------------------------------------------------------
    def configure_market(self) -> None:
        if self.paper:
            logs.info(f"[paper] skipping set_leverage / set_margin_mode (symbol={self.symbol})")
            return
        s = self.settings
        try:
            self.client.set_leverage(s.leverage, self.symbol)
        except Exception as e:  # noqa: BLE001
            logs.error(f"set_leverage failed: {e}")
        try:
            self.client.set_margin_mode(s.margin_mode, self.symbol)
        except Exception as e:  # noqa: BLE001
            msg = str(e).lower()
            if "no need to change" not in msg and "already" not in msg:
                logs.error(f"set_margin_mode failed: {e}")

    # ---- data (public — work without keys) -----------------------------
    def fetch_ohlcv(self, timeframe: str, limit: int = 500) -> list[list[float]]:
        return self.client.fetch_ohlcv(self.symbol, timeframe=timeframe, limit=limit)

    def fetch_last_price(self) -> float:
        t = self.client.fetch_ticker(self.symbol)
        return float(t["last"])

    # ---- account / positions -------------------------------------------
    def fetch_balance_usdt(self) -> float:
        if self.paper:
            return self._paper_balance
        try:
            bal = _retry(self.client.fetch_balance)
            total = bal.get("total", {}).get("USDT") or bal.get("USDT", {}).get("total")
            return float(total or 0.0)
        except Exception as e:  # noqa: BLE001
            logs.error(f"fetch_balance failed: {type(e).__name__}: {e!r}")
            return 0.0

    def fetch_position(self) -> dict[str, Any] | None:
        if self.paper:
            return self._paper_position
        try:
            positions = _retry(lambda: self.client.fetch_positions([self.symbol]))
            for p in positions:
                contracts = float(p.get("contracts") or 0)
                if contracts != 0:
                    return p
        except Exception as e:  # noqa: BLE001
            logs.error(f"fetch_positions failed: {type(e).__name__}: {e!r}")
        return None

    # ---- orders --------------------------------------------------------
    def _live_allowed(self) -> bool:
        if self.paper:
            return True
        if not self.settings.live_enabled and not self.settings.bitget_testnet:
            logs.info("LIVE_ENABLED=false and not on testnet → skipping order placement.")
            return False
        return True

    def market_order(
        self,
        side: str,
        qty: float,
        sl: float | None = None,
        tp: float | None = None,
    ) -> dict[str, Any] | None:
        """Place a market order with optional attached SL/TP (Bitget bracket)."""
        if not self._live_allowed():
            return None
        if self.paper:
            price = self.fetch_last_price()
            self._paper_position = {
                "symbol": self.symbol,
                "side": "long" if side.upper() == "BUY" else "short",
                "contracts": qty,
                "entryPrice": price,
            }
            if sl is not None:
                self._paper_sl = sl
            if tp is not None:
                self._paper_tp = tp
            self._save_paper_state()
            return {"id": "paper", "price": price, "amount": qty, "side": side.lower()}
        params: dict[str, Any] = {"marginCoin": "USDT", "productType": "USDT-FUTURES"}
        if sl is not None:
            params["presetStopLossPrice"] = float(self.client.price_to_precision(self.symbol, sl))
        if tp is not None:
            params["presetStopSurplusPrice"] = float(self.client.price_to_precision(self.symbol, tp))
        return self.client.create_order(self.symbol, "market", side.lower(), qty, None, params)

    def stop_loss(self, side: str, qty: float, stop_price: float) -> dict[str, Any] | None:
        if not self._live_allowed():
            return None
        if self.paper:
            self._paper_sl = stop_price
            self._save_paper_state()
            return {"id": "paper-sl", "stopPrice": stop_price}
        opposite = "sell" if side.upper() == "BUY" else "buy"
        return self.client.create_order(
            self.symbol, "market", opposite, qty, None,
            {
                "marginCoin": "USDT",
                "productType": "USDT-FUTURES",
                "stopPrice": stop_price,
                "triggerPrice": stop_price,
                "reduceOnly": True,
                "triggerType": "mark_price",
            },
        )

    def take_profit(self, side: str, qty: float, tp_price: float) -> dict[str, Any] | None:
        if not self._live_allowed():
            return None
        if self.paper:
            self._paper_tp = tp_price
            self._save_paper_state()
            return {"id": "paper-tp", "stopPrice": tp_price}
        opposite = "sell" if side.upper() == "BUY" else "buy"
        return self.client.create_order(
            self.symbol, "market", opposite, qty, None,
            {
                "marginCoin": "USDT",
                "productType": "USDT-FUTURES",
                "stopPrice": tp_price,
                "triggerPrice": tp_price,
                "reduceOnly": True,
                "triggerType": "mark_price",
                "takeProfit": True,
            },
        )

    def flatten(self) -> None:
        if self.paper:
            if self._paper_position is None:
                return
            self._settle_paper(self.fetch_last_price())
            return
        try:
            self.client.cancel_all_orders(self.symbol)
        except Exception as e:  # noqa: BLE001
            logs.error(f"cancel_all_orders failed: {e}")
        pos = self.fetch_position()
        if not pos:
            return
        contracts = abs(float(pos["contracts"]))
        side = "sell" if pos["side"] == "long" else "buy"
        try:
            self.client.create_order(
                self.symbol, "market", side, contracts, None, {"reduceOnly": True}
            )
            logs.info(f"Flatten order sent: {side} {contracts}")
        except Exception as e:  # noqa: BLE001
            logs.error(f"flatten failed: {e}")

    # ---- paper helpers -------------------------------------------------
    def paper_check_brackets(self) -> Optional[float]:
        if not self.paper or self._paper_position is None:
            return None
        try:
            price = self.fetch_last_price()
        except Exception:  # noqa: BLE001
            return None
        side = self._paper_position["side"]
        sl, tp = self._paper_sl, self._paper_tp
        hit: Optional[float] = None
        if side == "long":
            if sl is not None and price <= sl:
                hit = sl
            elif tp is not None and price >= tp:
                hit = tp
        else:
            if sl is not None and price >= sl:
                hit = sl
            elif tp is not None and price <= tp:
                hit = tp
        if hit is None:
            return None
        self._settle_paper(hit)
        return hit

    def _settle_paper(self, exit_price: float) -> None:
        pos = self._paper_position
        if pos is None:
            return
        direction = 1 if pos["side"] == "long" else -1
        pnl = (exit_price - pos["entryPrice"]) * direction * pos["contracts"]
        self._paper_balance += pnl
        self._paper_position = None
        self._paper_sl = None
        self._paper_tp = None
        self._save_paper_state()
