from interactem.core.constants import SUBJECT_PIPELINES_DEPLOYMENTS, UPDATES
from interactem.core.events.deployments import DeploymentUpdateEvent
from interactem.core.logger import get_logger
from interactem.core.nats.broker import get_nats_broker
from interactem.core.nats.consumers import PIPELINE_UPDATE_CONSUMER_CONFIG
from interactem.core.nats.streams import DEPLOYMENTS_JSTREAM

from ..api.faststream_deps import OrchestratorApiKeyDep, SessionDep
from ..core.config import settings
from ..models import PipelineDeployment

logger = get_logger()

broker = get_nats_broker(servers=[str(settings.NATS_SERVER_URL)], name="app-broker")

pipeline_update_consumer_config = PIPELINE_UPDATE_CONSUMER_CONFIG
pipeline_update_consumer_config.description = "API pipeline updates consumer"


@broker.subscriber(
    stream=DEPLOYMENTS_JSTREAM,
    subject=f"{SUBJECT_PIPELINES_DEPLOYMENTS}.*.{UPDATES}",
    config=pipeline_update_consumer_config,
    pull_sub=True,
    description=pipeline_update_consumer_config.description,
    dependencies=[OrchestratorApiKeyDep],
)
async def pipeline_updates_consumer(update: DeploymentUpdateEvent, session: SessionDep):
    """
    Consume deployment state updates from the orchestrator and update the database.
    The orchestrator is the source of truth for deployment state transitions.
    """
    deployment = session.get(PipelineDeployment, update.deployment_id)
    if not deployment:
        raise ValueError(
            f"Pipeline deployment with ID {update.deployment_id} not found."
        )

    # Update deployment state from orchestrator event
    deployment.state = update.state
    session.add(deployment)
    session.commit()

    logger.info(f"Updated deployment {update.deployment_id} state to {update.state}")
