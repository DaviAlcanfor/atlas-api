"""v1.1 (spec 004, CR-002): glossary terms written by import-content from content/glossary.yaml."""
from fastapi import APIRouter

from atlas_api import queries
from atlas_api.deps import DbSession
from atlas_api.errors import NotFoundError
from atlas_api.schemas import GlossaryList, GlossaryTerm

router = APIRouter(prefix="/glossary", tags=["glossary"])


@router.get("")
def list_glossary(db: DbSession) -> GlossaryList:
    return GlossaryList(items=queries.list_glossary(db))


@router.get("/{id}")
def get_glossary_term(db: DbSession, id: str) -> GlossaryTerm:
    term = queries.get_glossary_term(db, id)
    if term is None:
        raise NotFoundError(f"Unknown glossary term {id}")
    return term
