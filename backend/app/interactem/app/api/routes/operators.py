
from fastapi import APIRouter

from interactem.app.api.deps import CurrentUser
from interactem.app.models import OperatorSpecs
from interactem.app.operators import fetch_operators
from interactem.core.logger import get_logger

logger = get_logger()
router = APIRouter()

_operators = None


@router.get("/", response_model=OperatorSpecs)
async def read_operators(current_user: CurrentUser) -> OperatorSpecs:
    """
    Retrieve available operators.
    """
    global _operators

    if _operators is None:
        _operators = await fetch_operators()

    return OperatorSpecs(data=_operators)
