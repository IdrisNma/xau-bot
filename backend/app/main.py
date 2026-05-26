"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlmodel import Session

from . import logs
from .api import router
from .db import BotConfig, engine, init_db
from .engine import get_engine
from .settings import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    logs.info("API ready.")
    # Auto-resume engine if DB says it was running before restart
    with Session(engine) as s:
        cfg = s.get(BotConfig, 1)
        if cfg and cfg.status == "running":
            try:
                await get_engine().start(cfg.strategy)
                logs.info(f"Auto-resumed engine [{cfg.strategy}] after restart")
            except Exception as e:  # noqa: BLE001
                logs.error(f"auto-resume failed: {type(e).__name__}: {e!r}")
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="XAU Bot", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.get("/health")
    def health():
        return {"ok": True, "symbol": s.symbol, "testnet": s.bitget_testnet}

    return app


app = create_app()
