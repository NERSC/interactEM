from fastapi import APIRouter

from interactem.app.api.deps import CurrentUser
from interactem.app.events.producer import publish_sfapi_submit_event
from interactem.core.logger import get_logger
from interactem.sfapi_models import JobSubmitEvent

logger = get_logger()
router = APIRouter()


@router.post("/launch")
async def launch_agent(current_user: CurrentUser, job_request: JobSubmitEvent) -> None:
    """
    Launch an agent remotely.
    """
    await publish_sfapi_submit_event(job_request)
