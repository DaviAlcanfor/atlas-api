"""FastAPI dependencies: routers declare what they need, the app provides it (dependency injection)."""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from atlas_api.db.session import get_session

DbSession = Annotated[Session, Depends(get_session)]
