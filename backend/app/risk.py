"""Risk management: position sizing + circuit breakers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from .db import Trade, engine
from .settings import get_settings


@dataclass
class SizingResult:
    qty: float
    notional: float
    rejected_reason: str | None = None


def size_position(
    equity: float,
    entry_price: float,
    stop_price: float,
    risk_pct: float,
    min_qty: float = 0.001,
    qty_step: float = 0.001,
) -> SizingResult:
    """Risk-based sizing: qty such that (entry-stop)*qty = equity*risk_pct."""
    if equity <= 0:
        return SizingResult(0.0, 0.0, "equity <= 0")
    stop_dist = abs(entry_price - stop_price)
    if stop_dist <= 0:
        return SizingResult(0.0, 0.0, "invalid stop distance")
    risk_amount = equity * risk_pct
    raw_qty = risk_amount / stop_dist
    # round down to step
    qty = max(0.0, (raw_qty // qty_step) * qty_step)
    if qty < min_qty:
        return SizingResult(0.0, 0.0, f"qty below min ({min_qty})")
    return SizingResult(qty=qty, notional=qty * entry_price)


@dataclass
class BreakerState:
    paused: bool
    reason: str | None = None


def check_circuit_breakers(starting_equity: float) -> BreakerState:
    """Pause trading if any breaker has tripped today (UTC)."""
    s = get_settings()
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    with Session(engine) as sess:
        trades_today = sess.exec(
            select(Trade).where(Trade.opened_at >= today_start)
        ).all()

    closed = [t for t in trades_today if t.pnl is not None]
    pnl_today = sum(t.pnl for t in closed)  # type: ignore[union-attr]
    if starting_equity > 0 and pnl_today <= -starting_equity * s.daily_max_loss_pct:
        return BreakerState(True, f"daily max loss hit ({pnl_today:.2f})")

    if len(trades_today) >= s.max_trades_per_day:
        return BreakerState(True, f"max trades per day reached ({s.max_trades_per_day})")

    # Cooldown after a stop-loss
    losses = [t for t in closed if t.outcome == "LOSS"]
    if losses:
        last_loss = max(losses, key=lambda t: t.closed_at or datetime.min)
        if last_loss.closed_at and (
            datetime.utcnow() - last_loss.closed_at
            < timedelta(seconds=s.cooldown_seconds_after_sl)
        ):
            return BreakerState(True, "cooldown after stop loss")

    return BreakerState(False, None)
