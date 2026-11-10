from fastapi import APIRouter

from atlas_api.deps import Store
from atlas_api.schemas import Meta

router = APIRouter(tags=["system"])


@router.get("/meta")
def get_meta(store: Store) -> Meta:
    return store.meta
