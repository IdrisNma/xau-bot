"""REST and WebSocket routes."""
from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from . import logs
from .db import BotConfig, EquityPoint, LogEntry, Trade, engine
from .engine import get_engine
from .settings import get_settings
from .strategies.presets import PRESETS

router = APIRouter()
_auth = HTTPBearer(auto_error=False)


def require_token(creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_auth)]):
    expected = get_settings().api_bearer_token
    if not creds or creds.credentials != expected:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid bearer token")


@router.get("/bot")
def get_bot():
    with Session(engine) as s:
        cfg = s.get(BotConfig, 1)
        return {
            "strategy": cfg.strategy if cfg else "balanced",
            "status": cfg.status if cfg else "stopped",
            "started_at": cfg.started_at,
            "starting_equity": cfg.starting_equity,
            "paused_reason": cfg.paused_reason,
            "symbol": get_settings().symbol,
            "testnet": get_settings().bitget_testnet,
            "live_enabled": get_settings().live_enabled,
            "strategies": list(PRESETS.keys()),
        }


@router.post("/bot/start", dependencies=[Depends(require_token)])
async def start_bot(payload: dict = Body(default={})):
    name = payload.get("strategy") or get_settings().default_strategy
    if name not in PRESETS:
        raise HTTPException(400, f"unknown strategy: {name}")
    await get_engine().start(name)
    return {"ok": True, "strategy": name}


@router.post("/bot/stop", dependencies=[Depends(require_token)])
async def stop_bot():
    await get_engine().stop(flatten=True)
    return {"ok": True}


@router.delete("/bot", dependencies=[Depends(require_token)])
async def delete_bot():
    await get_engine().delete()
    return {"ok": True}


@router.get("/trades")
def list_trades(limit: int = 50):
    with Session(engine) as s:
        rows = s.exec(select(Trade).order_by(Trade.id.desc()).limit(limit)).all()
        return [r.model_dump() for r in rows]


@router.get("/logs")
def list_logs(limit: int = 200):
    # Prefer in-memory buffer for fast warm-start; fall back to DB if empty.
    buf = logs.recent(limit)
    if buf:
        return buf
    with Session(engine) as s:
        rows = s.exec(select(LogEntry).order_by(LogEntry.id.desc()).limit(limit)).all()
        rows = list(reversed(rows))
        return [
            {"ts": r.ts.isoformat() + "Z", "level": r.level, "category": r.category,
             "message": r.message}
            for r in rows
        ]


@router.get("/stats")
def stats():
    with Session(engine) as s:
        trades = s.exec(select(Trade)).all()
        cfg = s.get(BotConfig, 1)
    closed = [t for t in trades if t.pnl is not None]
    wins = [t for t in closed if (t.pnl or 0) > 0]
    win_rate = (len(wins) / len(closed) * 100) if closed else 0.0
    profit = sum((t.pnl or 0) for t in closed)
    last_trade = trades[-1].model_dump() if trades else None
    try:
        balance = get_engine().exchange.fetch_balance_usdt()
    except Exception:  # noqa: BLE001
        balance = None
    starting = cfg.starting_equity if cfg else None
    return {
        "trades": len(trades),
        "closed": len(closed),
        "win_rate": round(win_rate, 1),
        "profit": round(profit, 2),
        "balance": round(balance, 2) if balance is not None else None,
        "starting_equity": round(starting, 2) if starting else None,
        "last_trade": last_trade,
    }


@router.post("/bot/trade", dependencies=[Depends(require_token)])
async def manual_trade(payload: dict = Body(...)):
    """Place a manual market order, bypassing the strategy signal.

    Body: { "side": "BUY"|"SELL", "qty": float, "sl": float|null,
            "tp": float|null,  # single TP (legacy)
            "tps": [float, ...] }  # multi-TP: splits qty across N orders
    qty=0 means auto-size total from current equity using risk_pct.
    """
    from .db import Trade
    from .risk import size_position

    side = str(payload.get("side", "")).upper()
    if side not in ("BUY", "SELL"):
        raise HTTPException(400, "side must be BUY or SELL")

    sl: float | None = float(payload["sl"]) if payload.get("sl") else None
    qty_raw: float = float(payload.get("qty") or 0)

    # Normalize TPs: accept either "tps" array or single "tp"
    tps_in = payload.get("tps")
    if isinstance(tps_in, list):
        tps: list[float | None] = [float(x) for x in tps_in if x not in (None, "", 0)]
    elif payload.get("tp"):
        tps = [float(payload["tp"])]
    else:
        tps = [None]  # one order, no TP

    n_slices = max(1, len(tps))

    eng = get_engine()
    price = eng.exchange.fetch_last_price()
    equity_val = eng.exchange.fetch_balance_usdt() or get_settings().leverage * 10

    if qty_raw <= 0:
        stop_price = sl if sl is not None else (price * 0.995 if side == "BUY" else price * 1.005)
        sized = size_position(
            equity=equity_val,
            entry_price=price,
            stop_price=stop_price,
            risk_pct=get_settings().risk_pct,
        )
        if sized.qty <= 0:
            raise HTTPException(400, f"auto-sizing rejected: {sized.rejected_reason}")
        max_notional = equity_val * get_settings().leverage * 0.9
        if sized.notional > max_notional:
            capped = (max_notional / price // 0.001) * 0.001
            if capped < 0.001:
                raise HTTPException(400, "insufficient margin for minimum qty")
            sized.qty = capped
        total_qty = sized.qty
    else:
        total_qty = qty_raw

    # Split total qty into n_slices, rounded down to 0.001 step. Drop slices that would be too small.
    MIN_QTY = 0.001
    slice_qty = (total_qty / n_slices // MIN_QTY) * MIN_QTY
    if slice_qty < MIN_QTY:
        # Can't split that many ways — collapse to single order with first TP only
        slice_qty = (total_qty // MIN_QTY) * MIN_QTY
        if slice_qty < MIN_QTY:
            raise HTTPException(400, f"qty {total_qty} below minimum after split")
        tps = tps[:1]
        n_slices = 1

    placed: list[dict] = []
    sym = get_settings().symbol
    for i, tp_i in enumerate(tps):
        try:
            eng.exchange.market_order(side, slice_qty, sl=sl, tp=tp_i)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(500, f"order {i+1}/{n_slices} failed: {e}") from e

        with Session(engine) as s:
            tr = Trade(
                symbol=sym,
                side=side,
                entry_price=price,
                qty=slice_qty,
                sl=sl,
                tp=tp_i,
                outcome="OPEN",
                strategy="manual",
                reason=f"Manual trade {i+1}/{n_slices} via dashboard",
            )
            s.add(tr)
            s.commit()
            s.refresh(tr)
            eng._open_trade_ids.add(tr.id)  # type: ignore[arg-type]
            placed.append({"id": tr.id, "qty": slice_qty, "tp": tp_i})

        log_fn = logs.buy if side == "BUY" else logs.sell
        tp_str = f"${tp_i:.2f}" if tp_i else "none"
        log_fn(f"MANUAL {side} {sym} {i+1}/{n_slices} @ ${price:.2f} qty={slice_qty} SL={sl} TP={tp_str}")

    return {
        "ok": True, "side": side, "entry": price, "sl": sl,
        "slices": placed, "total_qty": slice_qty * n_slices,
    }


@router.get("/equity")
def equity(limit: int = 500):
    with Session(engine) as s:
        rows = s.exec(select(EquityPoint).order_by(EquityPoint.id.desc()).limit(limit)).all()
        rows = list(reversed(rows))
        return [{"ts": r.ts.isoformat() + "Z", "equity": r.equity} for r in rows]


# ---- WebSocket ---------------------------------------------------------

@router.websocket("/ws")
async def ws(websocket: WebSocket):
    # Token via query string (?token=...) since browsers can't send Authorization on WS easily.
    token = websocket.query_params.get("token")
    if token != get_settings().api_bearer_token:
        await websocket.close(code=4401)
        return
    await websocket.accept()
    # Warm-start with recent buffer
    for entry in logs.recent(200):
        await websocket.send_json({"type": "log", "data": entry})
    q = logs.subscribe()
    try:
        while True:
            entry = await q.get()
            try:
                await websocket.send_json({"type": "log", "data": entry})
            except (WebSocketDisconnect, RuntimeError):
                break
    except WebSocketDisconnect:
        pass
    finally:
        logs.unsubscribe(q)
