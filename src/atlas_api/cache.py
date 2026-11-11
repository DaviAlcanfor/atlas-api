"""HTTP caching required by the contract: X-Data-Version, weak ETag, Cache-Control, 304.

The data only changes when `import-content` runs (new data_version), so the ETag is a hash of
(data_version, path, query): no need to hash bodies. Applied to every /v1 response except
/v1/health. ETag and Cache-Control only go on 2xx responses (a cached 404 would keep hiding
content added later); X-Data-Version goes on everything.
"""

import hashlib
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from sqlalchemy.exc import SQLAlchemyError

from atlas_api import queries
from atlas_api.errors import problem

CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=86400"
_NO_CACHE_PATHS = {"/v1/health"}


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
        with factory() as session:  # one cheap PK lookup; the version changes only on import
            version = queries.data_version(session)
    except SQLAlchemyError:
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
