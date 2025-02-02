from fastapi import APIRouter

from interactem.app.api.deps import CurrentUser
from interactem.app.events.producer import request_agent_start
from interactem.core.logger import get_logger
from interactem.sfapi_models import JobSubmitRequest, JobSubmitResponse

logger = get_logger()
router = APIRouter()

_operators = None


@router.post("/launch", response_model=JobSubmitResponse)
async def launch_agent(
    current_user: CurrentUser, job_request: JobSubmitRequest
) -> JobSubmitResponse:
    """
    Launch an agent on Perlmutter
    """
    rep = await request_agent_start(job_request)
    return JobSubmitResponse.model_validate_json(rep.data)
