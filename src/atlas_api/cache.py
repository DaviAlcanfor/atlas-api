"""HTTP caching required by the contract: X-Data-Version, weak ETag, Cache-Control, 304.

The data only changes when `import-content` runs (new data_version), so the ETag is a hash of
(data_version, path, query): no need to hash bodies. Applied to every /v1 response except
/v1/health. ETag and Cache-Control only go on 2xx responses (a cached 404 would keep hiding
content added later); X-Data-Version goes on everything.
"""

import hashlib
import time
from collections.abc import Awaitable, Callable

import anyio
from fastapi import Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from atlas_api import queries
from atlas_api.config import get_settings
from atlas_api.errors import problem

CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=86400"
_NO_CACHE_PATHS = {"/v1/health"}


async def _data_version(request: Request, factory: Callable[[], Session]) -> str:
    """meta.data_version, cached per process for DATA_VERSION_TTL seconds. The lookup runs in a
    worker thread: a blocking DB call here would freeze the event loop for every request (spec 019
    item 5: under a burst it waited on the pool while holding up the very requests that free it)."""
    cached = getattr(request.app.state, "data_version", None)
    if cached and time.monotonic() - cached[1] < get_settings().data_version_ttl:
        return str(cached[0])

    def lookup() -> str:
        with factory() as session:  # one cheap PK lookup; the version changes only on import
            return queries.data_version(session)

    version = await anyio.to_thread.run_sync(lookup)
    request.app.state.data_version = (version, time.monotonic())
    return version


def make_etag(data_version: str, path: str, query: str) -> str:
    digest = hashlib.sha256(f"{data_version}|{path}|{query}".encode()).hexdigest()[:20]
    return f'W/"{digest}"'


def _matches(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    tags = [t.strip() for t in if_none_match.split(",")]
    return "*" in tags or etag in tags


async def add_cache_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    factory = getattr(request.app.state, "session_factory", None)
    if request.method != "GET" or request.url.path in _NO_CACHE_PATHS or factory is None:
        return await call_next(request)
    try:
        version = await _data_version(request, factory)
    except SQLAlchemyError:  # includes the pool timeout: a saturated pool answers 503 fast
        return problem(503, "Database unavailable.")
    etag = make_etag(version, request.url.path, request.url.query)
    if _matches(request.headers.get("if-none-match"), etag):
        # 304 skips the work: no route runs, no body is sent.
        return Response(
            status_code=304,
            headers={"ETag": etag, "X-Data-Version": version, "Cache-Control": CACHE_CONTROL},
        )
    response = await call_next(request)
    response.headers["X-Data-Version"] = version
    if 200 <= response.status_code < 300:
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = CACHE_CONTROL
    return response
