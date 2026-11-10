"""FastAPI dependencies: routers declare what they need, the app provides it (dependency injection)."""
from typing import Annotated

from fastapi import Depends, Request

from atlas_api.fixtures import FixtureStore


def get_store(request: Request) -> FixtureStore:
    store: FixtureStore = request.app.state.store
    return store


Store = Annotated[FixtureStore, Depends(get_store)]
