from uuid import UUID

from fastapi import APIRouter

from interactem.app.api.deps import CurrentUser
from interactem.app.events.producer import (
    publish_agent_shutdown_event,
    publish_sfapi_submit_event,
)
from interactem.core.events.agents import AgentShutdownEvent
from interactem.core.logger import get_logger
from interactem.sfapi_models import AgentCreateEvent

logger = get_logger()
router = APIRouter()

@router.post("/launch")
async def launch_agent(current_user: CurrentUser, agent_req: AgentCreateEvent) -> None:
    """
    Launch an agent remotely.
    """
    await publish_sfapi_submit_event(agent_req)


@router.post("/{agent_id}/shutdown")
async def shutdown_agent(current_user: CurrentUser, agent_id: UUID) -> None:
    """
    Request an agent shutdown.
    """
    await publish_agent_shutdown_event(AgentShutdownEvent(agent_id=agent_id))
