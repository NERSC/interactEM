from interactem.core.constants import SUBJECT_PIPELINES_UPDATES
from interactem.core.events.pipelines import PipelineUpdateEvent
from interactem.core.logger import get_logger
from interactem.core.nats.broker import get_nats_broker
from interactem.core.nats.config import PIPELINES_FASTSTREAM_CONFIG
from interactem.core.nats.consumers import PIPELINE_UPDATE_CONSUMER_CONFIG

from ..api.faststream_deps import OrchestratorApiKeyDep, SessionDep
from ..api.routes.deployments import _handle_update_pipeline_state
from ..core.config import settings
from ..models import PipelineDeployment, PipelineDeploymentUpdate

logger = get_logger()

broker = get_nats_broker(servers=[str(settings.NATS_SERVER_URL)], name="app-broker")

pipeline_update_consumer_config = PIPELINE_UPDATE_CONSUMER_CONFIG
pipeline_update_consumer_config.description = "API pipeline updates consumer"


@broker.subscriber(
    stream=PIPELINES_FASTSTREAM_CONFIG,
    subject=f"{SUBJECT_PIPELINES_UPDATES}",
    config=pipeline_update_consumer_config,
    pull_sub=True,
    description=pipeline_update_consumer_config.description,
    dependencies=[OrchestratorApiKeyDep],
)
async def pipeline_updates_consumer(update: PipelineUpdateEvent, session: SessionDep):
    _update = PipelineDeploymentUpdate.model_validate(update)
    deployment = session.get(PipelineDeployment, update.deployment_id)
    if not deployment:
        raise ValueError(
            f"Pipeline deployment with ID {update.deployment_id} not found."
        )
    await _handle_update_pipeline_state(session, deployment, _update)
