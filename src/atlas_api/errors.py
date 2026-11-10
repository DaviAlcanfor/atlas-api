"""Domain exceptions and their mapping to application/problem+json (the contract error shape)."""
import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("atlas_api")


class AtlasError(Exception):
    """Base for errors raised on purpose. Subclasses set the HTTP status."""

    status = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class NotFoundError(AtlasError):
    status = HTTPStatus.NOT_FOUND


class InvalidParameterError(AtlasError):
    """Value is well-formed but not acceptable (e.g. year outside the data range)."""

    status = HTTPStatus.UNPROCESSABLE_ENTITY


class ServiceUnavailableError(AtlasError):
    """Database or another dependency is down."""

    status = HTTPStatus.SERVICE_UNAVAILABLE


def problem(status: int, detail: str, title: str | None = None) -> JSONResponse:
    return JSONResponse(
        {
            "type": "about:blank",
            "title": title or HTTPStatus(status).phrase,
            "status": status,
            "detail": detail,
        },
        status_code=status,
        media_type="application/problem+json",
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AtlasError)
    async def _atlas(_: Request, exc: AtlasError) -> JSONResponse:
        return problem(exc.status, exc.detail)

    @app.exception_handler(StarletteHTTPException)  # unknown route (404), wrong method (405)...
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)  # malformed query/path params -> 422
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        detail = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        return problem(422, detail, "Invalid parameter")

    @app.exception_handler(Exception)  # anything unexpected: log it, never leak internals
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error on %s", request.url.path)
        return problem(500, "Unexpected server error.")
