from collections.abc import Callable
from dataclasses import replace
from uuid import uuid4

from faststream import ContextRepo as ContextRepoAnnotation
from faststream import FastStream
from faststream.context import ContextRepo
from faststream.nats.annotations import NatsBroker as BrokerAnnotation
from pydantic import BaseModel

from interactem.core.constants import (
    SUBJECT_PIPELINES_DEPLOYMENTS,
)
from interactem.core.events.pipelines import (
    PipelineEvent,
    PipelineRunEvent,
    PipelineStopEvent,
    PipelineUpdateEvent,
)
from interactem.core.logger import get_logger
from interactem.core.models.base import IdType, PipelineDeploymentState
from interactem.core.models.runtime import (
    RuntimePipeline,
)
from interactem.core.nats.broker import get_nats_broker
from interactem.core.nats.consumers import DEPLOYMENTS_CONSUMER_CONFIG
from interactem.core.nats.publish import (
    create_deployment_status_publisher,
    create_error_publisher,
    create_info_publisher,
)
from interactem.core.nats.streams import DEPLOYMENTS_JSTREAM

from .config import cfg
from .constants import (
    DEPLOYMENT_ID_CTX_NAME,
    DEPLOYMENT_STATUS_PUBLISHER_CTX_NAME,
    ERROR_PUBLISHER_CTX_NAME,
    INFO_PUBLISHER_CTX_NAME,
)
from .exceptions import PipelineExceptionMiddleware
from .orchestrator import (
    handle_run_pipeline,
    handle_stop_pipeline_event,
)

"""
This is a bit confusing, so to clarify:
1. broker/app are main constructs of faststream
2. we provide a middleware to the app that handles exceptions, and then publishes
out updates
3. we are putting several different publishers into the context "repo", which is like a
dict that we can pass around in the functions that are wrapped by faststream

When we get a message, it comes in already deserialized into a PipelineEvent object,
and we look up the appropriate handler function for that event type, and we call it.
If an exception is raised it will be sent to this middleware
"""

logger = get_logger()
pipelines: dict[IdType, RuntimePipeline] = {}
orchestrator_id = uuid4()

broker = get_nats_broker(
    [str(cfg.NATS_SERVER_URL)],
    name=f"orchestrator-{orchestrator_id}",
    middlewares=(PipelineExceptionMiddleware,),  # type: ignore[arg-type]
)

# publishers
error_pub = create_error_publisher(
    broker=broker,
    id=orchestrator_id,
)
info_pub = create_info_publisher(
    broker=broker,
    id=orchestrator_id,
)
depl_status_update_pub = create_deployment_status_publisher(
    broker, cfg.ORCHESTRATOR_API_KEY
)

context_repo = ContextRepo(
    {
        ERROR_PUBLISHER_CTX_NAME: error_pub,
        INFO_PUBLISHER_CTX_NAME: info_pub,
        DEPLOYMENT_STATUS_PUBLISHER_CTX_NAME: depl_status_update_pub,
    }
)


HANDLERS: dict[type[BaseModel], Callable] = {
    PipelineRunEvent: handle_run_pipeline,
    PipelineStopEvent: handle_stop_pipeline_event,
}


@broker.subscriber(
    stream=DEPLOYMENTS_JSTREAM,
    subject=f"{SUBJECT_PIPELINES_DEPLOYMENTS}",
    config=replace(
        DEPLOYMENTS_CONSUMER_CONFIG, description=f"orchestrator-{orchestrator_id}"
    ),
    pull_sub=True,
)
async def handle_deployment_event(
    event: PipelineEvent,
    broker: BrokerAnnotation,
    context: ContextRepoAnnotation,
):
    # TODO: have to do this until this changes in faststream:
    # https://github.com/ag2ai/faststream/pull/2619
    js = broker.config.connection_state.stream

    logger.info(f"Received pipeline deployment event ({event.root.type})")
    handler = HANDLERS.get(type(event.root))
    context.set_local(DEPLOYMENT_ID_CTX_NAME, event.root.deployment_id)

    if not handler:
        raise NotImplementedError(f"No handler for event type {event.root.type}")

    await handler(event.root, js)

    if handler == handle_run_pipeline:
        await depl_status_update_pub.publish(
            PipelineUpdateEvent(
                deployment_id=event.root.deployment_id,
                state=PipelineDeploymentState.RUNNING,
            )
            .model_dump_json()
            .encode()
        )


app = FastStream(
    broker,
    logger=logger,
    context=context_repo,
)
