"""Logging: loguru sink that fan-outs to DB + in-memory pub/sub for WebSocket clients."""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
from typing import Any

from loguru import logger
from sqlmodel import Session

from .db import LogEntry, engine
from .settings import get_settings

_settings = get_settings()

# Ring buffer of recent log entries (dicts) for warm-start on WS connect.
_buffer: deque[dict[str, Any]] = deque(maxlen=_settings.log_retention)

# Active asyncio.Queues, one per WS subscriber.
_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()


def _persist(level: str, category: str, message: str, ts: datetime) -> None:
    try:
        with Session(engine) as s:
            s.add(LogEntry(ts=ts, level=level, category=category, message=message))
            s.commit()
    except Exception:  # pragma: no cover - never let logging crash the engine
        pass


def emit(level: str, message: str, category: str = "general") -> None:
    """Emit a structured log entry. Safe to call from sync or async code."""
    ts = datetime.utcnow()
    entry = {
        "ts": ts.isoformat() + "Z",
        "level": level,
        "category": category,
        "message": message,
    }
    _buffer.append(entry)
    _persist(level, category, message, ts)
    logger.log("INFO" if level not in {"ERROR", "WARNING"} else level, f"[{level}] {message}")
    # Fan-out to subscribers.
    for q in list(_subscribers):
        try:
            q.put_nowait(entry)
        except asyncio.QueueFull:  # pragma: no cover
            pass


def recent(limit: int = 200) -> list[dict[str, Any]]:
    return list(_buffer)[-limit:]


def subscribe() -> asyncio.Queue[dict[str, Any]]:
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
    _subscribers.add(q)
    return q


def unsubscribe(q: asyncio.Queue[dict[str, Any]]) -> None:
    _subscribers.discard(q)


# Convenience level helpers — these mirror the dashboard color rules.
def info(msg: str, category: str = "general") -> None: emit("INFO", msg, category)
def analysis(msg: str) -> None: emit("ANALYSIS", msg, "analysis")
def buy(msg: str) -> None: emit("BUY", msg, "trade")
def sell(msg: str) -> None: emit("SELL", msg, "trade")
def profit(msg: str) -> None: emit("PROFIT", msg, "trade")
def loss(msg: str) -> None: emit("LOSS", msg, "trade")
def error(msg: str) -> None: emit("ERROR", msg, "error")
