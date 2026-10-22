"""Aplicación FastAPI de PickMaster."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.db import create_all, setup_engine

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Crea el esquema al arrancar (Fase 1)."""
    create_all(setup_engine())
    yield


def create_app() -> FastAPI:
    """App lista para uvicorn."""
    application = FastAPI(
        title="PickMaster",
        description="Picks probabilísticos Liga MX · Draftea. No garantiza resultados.",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(router)
    return application


app = create_app()
