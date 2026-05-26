"""SQLModel database models and engine."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine

from .settings import get_settings


class BotConfig(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    strategy: str = "balanced"
    status: str = "stopped"  # stopped | running | paused
    started_at: Optional[datetime] = None
    starting_equity: Optional[float] = None
    paused_reason: Optional[str] = None


class Trade(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str
    side: str  # BUY | SELL
    entry_price: float
    exit_price: Optional[float] = None
    qty: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    pnl: Optional[float] = None
    outcome: Optional[str] = None  # WIN | LOSS | BE | OPEN
    opened_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None
    reason: Optional[str] = None
    strategy: Optional[str] = None


class LogEntry(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow)
    level: str = "INFO"  # INFO | BUY | SELL | PROFIT | LOSS | ERROR | ANALYSIS
    category: str = "general"
    message: str


class EquityPoint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow)
    equity: float


_settings = get_settings()
engine = create_engine(
    _settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {},
)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    # Ensure a single BotConfig row exists.
    with Session(engine) as s:
        cfg = s.get(BotConfig, 1)
        if cfg is None:
            s.add(BotConfig(id=1, strategy=_settings.default_strategy))
            s.commit()


def get_session() -> Session:
    return Session(engine)
