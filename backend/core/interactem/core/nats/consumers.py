from dataclasses import replace
from uuid import UUID

from faststream.nats.broker import NatsBroker
from faststream.nats.subscriber.asyncapi import AsyncAPISubscriber
from nats.js import JetStreamContext
from nats.js.api import (
    ConsumerConfig,
    DeliverPolicy,
)

from interactem.core.constants import (
    STREAM_DEPLOYMENTS,
    STREAM_METRICS,
    STREAM_PARAMETERS,
    STREAM_SFAPI,
    SUBJECT_AGENTS_DEPLOYMENTS,
    SUBJECT_METRICS_ALL,
    SUBJECT_OPERATORS_DEPLOYMENTS,
    SUBJECT_OPERATORS_PARAMETERS_UPDATE,
    SUBJECT_PIPELINES_DEPLOYMENTS_NEW,
    SUBJECT_PIPELINES_DEPLOYMENTS_STOP,
    SUBJECT_SFAPI_JOBS,
)
from interactem.core.logger import get_logger
from interactem.core.models.canonical import CanonicalOperatorID
from interactem.core.models.runtime import (
    RuntimeOperatorID,
    RuntimeOperatorParameter,
)
from interactem.core.models.spec import ParameterSpecType

logger = get_logger()

AGENT_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.NEW,
    inactive_threshold=30,
)

SFAPI_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.NEW,
    inactive_threshold=30,
)

DEPLOYMENTS_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.LAST_PER_SUBJECT,
)

PIPELINE_UPDATE_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.NEW,
)

METRICS_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.LAST_PER_SUBJECT,
)


async def create_agent_consumer(
    js: JetStreamContext,
    agent_id: UUID,
) -> JetStreamContext.PullSubscription:
    subject = f"{SUBJECT_AGENTS_DEPLOYMENTS}.{agent_id}"
    cfg = replace(AGENT_CONSUMER_CONFIG, description=f"agent-{agent_id}")
    psub = await js.pull_subscribe(
        stream=STREAM_DEPLOYMENTS,
        subject=subject,
        config=cfg,
    )
    logger.info(f"Subscribed to {subject}")
    return psub


def create_agent_mount_consumer(
    broker: NatsBroker,
    agent_id: UUID,
    canonical_operator_id: CanonicalOperatorID,
    parameter: RuntimeOperatorParameter,
) -> AsyncAPISubscriber:
    if parameter.type != ParameterSpecType.MOUNT:
        raise ValueError(
            f"Parameter {parameter.name} of type {parameter.type} is not a mount type."
        )
    subject = f"{SUBJECT_OPERATORS_PARAMETERS_UPDATE}.{canonical_operator_id}.{parameter.name}"
    cfg = replace(
        PIPELINE_UPDATE_CONSUMER_CONFIG,
        description=f"agent-{agent_id}-{canonical_operator_id}-{parameter.name}",
    )
    return broker.subscriber(
        stream=STREAM_PARAMETERS,
        subject=subject,
        config=cfg,
        pull_sub=True,
    )


async def create_operator_parameter_consumer(
    js: JetStreamContext,
    operator_id: CanonicalOperatorID,
) -> JetStreamContext.PullSubscription:
    subject = f"{SUBJECT_OPERATORS_PARAMETERS_UPDATE}.{operator_id}.>"
    cfg = replace(
        PIPELINE_UPDATE_CONSUMER_CONFIG,
        description=f"operator-{operator_id}",
    )
    psub = await js.pull_subscribe(
        stream=STREAM_PARAMETERS,
        subject=subject,
        config=cfg,
    )
    # TODO: Things like "offsets.emd" with file suffixes will be consumed on a offsets.emd.
    # We need to make a better way to handle file names as parameters.
    logger.info(f"Subscribed to {subject}")
    return psub


async def create_operator_pipeline_consumer(
    js: JetStreamContext,
    operator_id: RuntimeOperatorID,
) -> JetStreamContext.PullSubscription:
    subject = f"{SUBJECT_OPERATORS_DEPLOYMENTS}.{operator_id}"
    cfg = replace(
        DEPLOYMENTS_CONSUMER_CONFIG,
        description=f"operator-pipelines-{operator_id}",
    )
    psub = await js.pull_subscribe(
        stream=STREAM_DEPLOYMENTS,
        subject=subject,
        config=cfg,
    )
    logger.info(f"Subscribed to {subject}")
    return psub


async def create_orchestrator_deployment_consumer(
    js: JetStreamContext,
    orchestrator_id: UUID,
    subject: str,
) -> JetStreamContext.PullSubscription:
    cfg = replace(
        DEPLOYMENTS_CONSUMER_CONFIG,
        description=f"orchestrator-{orchestrator_id}",
    )
    psub = await js.pull_subscribe(
        stream=STREAM_DEPLOYMENTS,
        subject=subject,
        config=cfg,
    )
    logger.info(f"Subscribed to {subject}")
    return psub


# TODO: come back to this, did not want to change functionality significantly
# but I don't think we should be using "stop" and "new" in the subjects
async def create_orchestrator_pipeline_stop_consumer(
    js: JetStreamContext,
    orchestrator_id: UUID,
) -> JetStreamContext.PullSubscription:
    return await create_orchestrator_deployment_consumer(
        js,
        orchestrator_id,
        SUBJECT_PIPELINES_DEPLOYMENTS_STOP,
    )


async def create_orchestrator_pipeline_new_consumer(
    js: JetStreamContext,
    orchestrator_id: UUID,
) -> JetStreamContext.PullSubscription:
    return await create_orchestrator_deployment_consumer(
        js,
        orchestrator_id,
        SUBJECT_PIPELINES_DEPLOYMENTS_NEW,
    )


async def create_metrics_consumer(
    js: JetStreamContext,
) -> JetStreamContext.PullSubscription:
    subject = SUBJECT_METRICS_ALL
    cfg = replace(
        METRICS_CONSUMER_CONFIG,
        description="metrics-microservice-consumer",
    )
    psub = await js.pull_subscribe(
        stream=STREAM_METRICS,
        subject=subject,
        config=cfg,
    )
    logger.info(f"Subscribed to {subject}")
    return psub


async def create_sfapi_submit_consumer(
    js: JetStreamContext,
) -> JetStreamContext.PullSubscription:
    subject = SUBJECT_SFAPI_JOBS
    cfg = replace(
        SFAPI_CONSUMER_CONFIG,
        description="sfapi_submit_consumer",
    )
    psub = await js.pull_subscribe(
        stream=STREAM_SFAPI,
        subject=subject,
        config=cfg,
    )
    logger.info(f"Subscribed to {subject}")
    return psub
