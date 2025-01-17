import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from interactem.app.api.deps import CurrentUser, SessionDep

from interactem.app.models import Operators
from interactem.app.operators import fetch_operators
from interactem.core.logger import get_logger

logger = get_logger()
router = APIRouter()

_operators = None


@router.get("/", response_model=Operators)
async def read_operators(current_user: CurrentUser) -> Operators:
    """
    Retrieve available operators.
    """
    global _operators

    if _operators is None:
        _operators = await fetch_operators()

    return Operators(data=_operators)
