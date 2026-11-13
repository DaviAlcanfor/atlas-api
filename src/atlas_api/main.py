import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from atlas_api.cache import add_cache_headers
from atlas_api.config import get_settings
from atlas_api.db.session import make_engine, make_session_factory
from atlas_api.errors import register_error_handlers
from atlas_api.migrate import upgrade_to_head
from atlas_api.routers import (
    countries,
    economy,
    glossary,
    health,
    meta,
    polities,
    search,
    snapshots,
)


def create_app(database_url: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        """Startup: create the DB engine (the connection pool) and migrate the schema to head. Shutdown: close it."""
        logging.basicConfig(level=get_settings().log_level)
        st = get_settings()
        engine = make_engine(database_url or st.database_url, st.db_pool_size, st.db_max_overflow,
                             st.db_pool_timeout)
        if st.auto_migrate:
            upgrade_to_head(engine)
        app.state.engine = engine
        app.state.session_factory = make_session_factory(engine)
        yield
        engine.dispose()

    app = FastAPI(title="Atlas API", version="1.0", lifespan=lifespan)

    @app.middleware("http")
    async def cache_headers(request: Request, call_next: Any) -> Response:
        return await add_cache_headers(request, call_next)

    # Added last = outermost, so CORS answers preflights before anything else.
    # expose_headers: lets the browser JS read ETag / X-Data-Version (cross-origin).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
        expose_headers=["ETag", "X-Data-Version"],
    )
    register_error_handlers(app)
    for module in (health, meta, countries, polities, snapshots, search, glossary, economy):
        app.include_router(module.router, prefix="/v1")
    return app


app = create_app()
