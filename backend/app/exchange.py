"""Binance USDT-M Futures adapter (ccxt). Demo-trading-aware. Paper-mode fallback.

Modes (auto-detected):
- **paper**: no API key configured → orders simulated locally using public data.
- **demo**: ``BINANCE_TESTNET=true`` with valid keys from your real Binance account
  (Futures → Demo Trading → Generate Key) → uses ccxt demoTrading option.
- **live**: ``BINANCE_TESTNET=false`` AND ``LIVE_ENABLED=true`` AND valid keys.
  Otherwise order placement is short-circuited.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import ccxt

from . import logs
from .settings import get_settings


_PAPER_STATE_FILE = Path("paper_state.json")


class Exchange:
    def __init__(self) -> None:
        s = get_settings()
        self.settings = s
        self.symbol = s.symbol
        self.paper = not (s.binance_api_key and s.binance_api_secret)
        options: dict = {"defaultType": "future"}
        if s.binance_testnet and not self.paper:
            options["demoTrading"] = True
        self.client = ccxt.binanceusdm(
            {
                "apiKey": s.binance_api_key,
                "secret": s.binance_api_secret,
                "enableRateLimit": True,
                "options": options,
            }
        )

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
            bal = self.client.fetch_balance()
            total = bal.get("total", {}).get("USDT") or bal.get("USDT", {}).get("total")
            return float(total or 0.0)
        except Exception as e:  # noqa: BLE001
            logs.error(f"fetch_balance failed: {e}")
            return 0.0

    def fetch_position(self) -> dict[str, Any] | None:
        if self.paper:
            return self._paper_position
        try:
            positions = self.client.fetch_positions([self.symbol])
            for p in positions:
                contracts = float(p.get("contracts") or 0)
                if contracts != 0:
                    return p
        except Exception as e:  # noqa: BLE001
            logs.error(f"fetch_positions failed: {e}")
        return None

    # ---- orders --------------------------------------------------------
    def _live_allowed(self) -> bool:
        if self.paper:
            return True
        if not self.settings.live_enabled and not self.settings.binance_testnet:
            logs.info("LIVE_ENABLED=false and not on testnet → skipping order placement.")
            return False
        return True

    def market_order(self, side: str, qty: float) -> dict[str, Any] | None:
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
            self._save_paper_state()
            return {"id": "paper", "price": price, "amount": qty, "side": side.lower()}
        return self.client.create_order(self.symbol, "market", side.lower(), qty)

    def stop_loss(self, side: str, qty: float, stop_price: float) -> dict[str, Any] | None:
        if not self._live_allowed():
            return None
        if self.paper:
            self._paper_sl = stop_price
            self._save_paper_state()
            return {"id": "paper-sl", "stopPrice": stop_price}
        opposite = "sell" if side.upper() == "BUY" else "buy"
        return self.client.create_order(
            self.symbol, "STOP_MARKET", opposite, qty, None,
            {"stopPrice": stop_price, "reduceOnly": True, "workingType": "MARK_PRICE"},
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
            self.symbol, "TAKE_PROFIT_MARKET", opposite, qty, None,
            {"stopPrice": tp_price, "reduceOnly": True, "workingType": "MARK_PRICE"},
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
        """If a paper position's SL or TP was hit by current price, settle and
        return exit price. Otherwise return None."""
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
