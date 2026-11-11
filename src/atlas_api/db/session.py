"""Engine and session factory.

Engine = the connection pool (created once, in the app lifespan). Session = one unit of work
(a short-lived "conversation" with the DB), opened per request via the `get_session` dependency.
"""
from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str) -> Engine:
    # pool_pre_ping: test a pooled connection before using it (survives DB/pooler restarts).
    # connect_timeout: fail fast (seconds) when the DB is unreachable instead of hanging a request.
    return create_engine(
        url, pool_pre_ping=True, pool_size=5, max_overflow=5, connect_args={"connect_timeout": 5}
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session
