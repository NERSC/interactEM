
from fastapi import APIRouter, Query

from interactem.app.api.deps import CurrentUser
from interactem.app.models import OperatorSpecs
from interactem.app.operators import fetch_operators
from interactem.core.logger import get_logger

logger = get_logger()
router = APIRouter()

_operators = None


@router.get("/", response_model=OperatorSpecs)
async def read_operators(
    current_user: CurrentUser,
    refresh: bool = Query(False, description="Force refresh of operators cache"),
) -> OperatorSpecs:
    """
    Retrieve available operators. Use refresh=true to invalidate cache and fetch fresh data.
    """
    global _operators

    if refresh or _operators is None:
        if refresh:
            logger.info("Refreshing operators cache due to refresh parameter")
        _operators = await fetch_operators()

    ops = OperatorSpecs(data=_operators)
    logger.info(f"Operators found: {[op.image for op in ops.data]}")
    return ops
