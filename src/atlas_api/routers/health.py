from fastapi import APIRouter

from atlas_api.schemas import Health

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> Health:
    return Health(status="ok", db="ok")  # TODO Phase 1: real DB check
