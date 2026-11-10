import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas_api.config import get_settings
from atlas_api.errors import register_error_handlers
from atlas_api.fixtures import FixtureStore
from atlas_api.routers import countries, health, meta, polities, search, snapshots


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Runs once at startup (before `yield`) and shutdown (after).

    Fail fast: a broken fixture stops the app from booting instead of failing per request.
    """
    logging.basicConfig(level=get_settings().log_level)
    app.state.store = FixtureStore()  # Phase 1: create the DB engine here
    yield
    # shutdown: Phase 1 disposes the DB engine here


def create_app() -> FastAPI:
    app = FastAPI(title="Atlas API", version="1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    register_error_handlers(app)
    for module in (health, meta, countries, polities, snapshots, search):
        app.include_router(module.router, prefix="/v1")
    return app


app = create_app()
