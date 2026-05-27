"""Trading engine: orchestrates market data, strategy, risk and execution."""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from . import logs
from .db import BotConfig, EquityPoint, Trade, engine
from .exchange import Exchange
from .marketdata import MarketData
from .risk import check_circuit_breakers, size_position
from .settings import get_settings
from .strategies.base import Signal, Strategy
from .strategies.presets import get_preset
from .strategies.ta_classic import TAClassicStrategy


def build_strategy(preset_name: str) -> Strategy:
    return TAClassicStrategy(get_preset(preset_name))


class TradingEngine:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.exchange = Exchange()
        self.market = MarketData(self.exchange)
        self.strategy: Strategy = build_strategy(self.settings.default_strategy)
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._open_trade_id: Optional[int] = None

    # ---- lifecycle -----------------------------------------------------
    async def start(self, strategy_name: str | None = None) -> None:
        if self._task and not self._task.done():
            # Engine task already alive — just resync DB in case it drifted.
            with Session(engine) as s:
                cfg = s.get(BotConfig, 1)
                if cfg and cfg.status != "running":
                    cfg.status = "running"
                    cfg.paused_reason = None
                    s.add(cfg)
                    s.commit()
                    logs.info("Engine already running. Resynced DB status.")
                else:
                    logs.info("Engine already running.")
            return
        if strategy_name:
            self.strategy = build_strategy(strategy_name)
        with Session(engine) as s:
            cfg = s.get(BotConfig, 1)
            assert cfg is not None
            cfg.strategy = self.strategy.preset.name
            cfg.status = "running"
            cfg.started_at = datetime.utcnow()
            cfg.paused_reason = None
            if cfg.starting_equity is None or cfg.starting_equity <= 0:
                cfg.starting_equity = self.exchange.fetch_balance_usdt() or 1000.0
            s.add(cfg)
            s.commit()
        logs.info(f"Engine starting [{self.strategy.preset.name}] on {self.settings.symbol}")
        self.exchange.configure_market()
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self, flatten: bool = True) -> None:
        self._stop_event.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except asyncio.TimeoutError:
                self._task.cancel()
        if flatten:
            self.exchange.flatten()
            await self._reconcile_open_trade(reason="manual stop")
        with Session(engine) as s:
            cfg = s.get(BotConfig, 1)
            if cfg:
                cfg.status = "stopped"
                s.add(cfg)
                s.commit()
        logs.info("Engine stopped.")

    async def delete(self) -> None:
        """Stop, flatten, then wipe trades/logs/equity (keeps BotConfig row reset)."""
        await self.stop(flatten=True)
        with Session(engine) as s:
            for model in (Trade, EquityPoint):
                for row in s.exec(select(model)).all():
                    s.delete(row)
            cfg = s.get(BotConfig, 1)
            if cfg:
                cfg.status = "stopped"
                cfg.started_at = None
                cfg.starting_equity = None
                cfg.paused_reason = None
                s.add(cfg)
            s.commit()
        logs.info("Bot state cleared.")

    # ---- main loop -----------------------------------------------------
    async def _run(self) -> None:
        s = self.settings
        # Warm up frames
        try:
            self.market.backfill(s.signal_timeframe, limit=500)
            self.market.backfill(s.trend_timeframe, limit=300)
        except Exception as e:  # noqa: BLE001
            logs.error(f"backfill failed: {e}")
            # Don't leave DB status as 'running' with no loop alive.
            with Session(engine) as sess:
                cfg = sess.get(BotConfig, 1)
                if cfg:
                    cfg.status = "stopped"
                    cfg.paused_reason = f"backfill failed: {type(e).__name__}"
                    sess.add(cfg)
                    sess.commit()
            return

        while not self._stop_event.is_set():
            try:
                await self.market.wait_for_next_close(s.signal_timeframe)
                if self._stop_event.is_set():
                    break
                df_sig = self.market.refresh(s.signal_timeframe)
                df_trend = self.market.refresh(s.trend_timeframe)
                await self._on_tick(df_sig, df_trend)
            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001
                logs.error(f"engine loop error: {e}")
                await asyncio.sleep(5)

    async def _on_tick(self, df_sig, df_trend) -> None:
        # Paper mode: check whether SL/TP has been hit before evaluating new signal.
        if self.exchange.paper:
            self.exchange.paper_check_brackets()
        # Always check open position outcome first.
        await self._reconcile_open_trade()

        signal: Signal = self.strategy.evaluate(df_sig, df_trend)
        for note in signal.analysis_notes:
            logs.analysis(note)

        if signal.action == "HOLD":
            logs.analysis(f"No setup ({signal.reason}). Monitoring price action...")
            return

        # Circuit breakers
        with Session(engine) as s:
            cfg = s.get(BotConfig, 1)
            starting_equity = (cfg.starting_equity if cfg else None) or 1000.0
        br = check_circuit_breakers(starting_equity)
        if br.paused:
            logs.info(f"Circuit breaker active: {br.reason} — skipping signal.")
            with Session(engine) as s:
                cfg = s.get(BotConfig, 1)
                if cfg:
                    cfg.status = "paused"
                    cfg.paused_reason = br.reason
                    s.add(cfg)
                    s.commit()
            return

        if self._open_trade_id is not None:
            logs.info("Position already open, ignoring new signal.")
            return

        # Size + place order
        price = float(df_sig["close"].iloc[-1])
        equity = self.exchange.fetch_balance_usdt() or starting_equity
        sized = size_position(
            equity=equity,
            entry_price=price,
            stop_price=signal.sl or price,
            risk_pct=self.settings.risk_pct,
        )
        if sized.qty <= 0:
            logs.info(f"Sizing rejected: {sized.rejected_reason}")
            return
        # Cap qty so required margin fits inside available equity (90% buffer).
        max_notional = equity * self.settings.leverage * 0.9
        if sized.notional > max_notional:
            capped_qty = max(0.0, (max_notional / price))
            # round down to 0.001 step
            capped_qty = (capped_qty // 0.001) * 0.001
            if capped_qty < 0.001:
                logs.info(
                    f"Sizing capped to 0 by available margin "
                    f"(equity=${equity:.2f}, leverage={self.settings.leverage}x, "
                    f"notional=${sized.notional:.2f}, max=${max_notional:.2f})"
                )
                return
            logs.info(
                f"Sizing capped by margin: qty {sized.qty} → {capped_qty} "
                f"(equity=${equity:.2f}, max_notional=${max_notional:.2f})"
            )
            sized.qty = capped_qty
            sized.notional = capped_qty * price

        side = signal.action
        log_fn = logs.buy if side == "BUY" else logs.sell
        log_fn(f"{side} {self.settings.symbol} @ ${price:.2f} qty={sized.qty} ({signal.reason})")

        try:
            self.exchange.market_order(side, sized.qty)
            if signal.sl:
                self.exchange.stop_loss(side, sized.qty, signal.sl)
            if signal.tp:
                self.exchange.take_profit(side, sized.qty, signal.tp)
        except Exception as e:  # noqa: BLE001
            logs.error(f"order placement failed: {e}")
            return

        with Session(engine) as s:
            tr = Trade(
                symbol=self.settings.symbol,
                side=side,
                entry_price=price,
                qty=sized.qty,
                sl=signal.sl,
                tp=signal.tp,
                outcome="OPEN",
                strategy=self.strategy.preset.name,
                reason=signal.reason,
            )
            s.add(tr)
            s.commit()
            s.refresh(tr)
            self._open_trade_id = tr.id

    async def _reconcile_open_trade(self, reason: str | None = None) -> None:
        """If we recorded an open trade but exchange shows no position, close it in DB."""
        if self._open_trade_id is None:
            return
        pos = self.exchange.fetch_position()
        if pos is not None:
            return  # still open
        with Session(engine) as s:
            tr = s.get(Trade, self._open_trade_id)
            if not tr or tr.outcome != "OPEN":
                self._open_trade_id = None
                return
            exit_price = self.exchange.fetch_last_price()
            direction = 1 if tr.side == "BUY" else -1
            pnl = (exit_price - tr.entry_price) * direction * tr.qty
            tr.exit_price = exit_price
            tr.pnl = pnl
            tr.closed_at = datetime.utcnow()
            tr.outcome = "WIN" if pnl > 0 else ("LOSS" if pnl < 0 else "BE")
            if reason:
                tr.reason = (tr.reason or "") + f" | closed: {reason}"
            s.add(tr)
            # equity snapshot
            equity = self.exchange.fetch_balance_usdt()
            if equity:
                s.add(EquityPoint(equity=equity))
            s.commit()
        self._open_trade_id = None
        if pnl > 0:
            logs.profit(f"Position closed @ ${exit_price:.2f}  Profit: +${pnl:.2f}")
        elif pnl < 0:
            logs.loss(f"Position closed @ ${exit_price:.2f}  Loss: -${abs(pnl):.2f}")
        else:
            logs.info(f"Position closed @ ${exit_price:.2f}  Breakeven")


# Singleton accessor
_engine: TradingEngine | None = None


def get_engine() -> TradingEngine:
    global _engine
    if _engine is None:
        _engine = TradingEngine()
    return _engine
