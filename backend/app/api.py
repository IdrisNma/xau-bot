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
            "testnet": get_settings().binance_testnet,
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
