"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import logs
from .api import router
from .db import init_db
from .settings import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    logs.info("API ready.")
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
        return {"ok": True, "symbol": s.symbol, "testnet": s.binance_testnet}

    return app


app = create_app()
