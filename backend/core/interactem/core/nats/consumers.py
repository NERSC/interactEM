from dataclasses import replace
from uuid import UUID

from nats.js import JetStreamContext
from nats.js.api import (
    ConsumerConfig,
    DeliverPolicy,
)

from interactem.core.constants import (
    STREAM_AGENTS,
    STREAM_METRICS,
    STREAM_OPERATORS,
    STREAM_PARAMETERS,
    STREAM_PIPELINES,
    STREAM_SFAPI,
    SUBJECT_PIPELINES_RUN,
    SUBJECT_SFAPI_JOBS_SUBMIT,
)
from interactem.core.logger import get_logger
from interactem.core.models.operators import OperatorParameter
from interactem.core.models.pipeline import OperatorJSON

logger = get_logger()

AGENT_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.LAST_PER_SUBJECT,
    inactive_threshold=30,
)

SFAPI_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.NEW,
    inactive_threshold=30,
)

PARAMETER_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.LAST_PER_SUBJECT,
)

PIPELINE_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.LAST_PER_SUBJECT,
)

METRICS_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.LAST_PER_SUBJECT,
)


async def create_agent_consumer(
    js: JetStreamContext,
    agent_id: UUID,
) -> JetStreamContext.PullSubscription:
    subject = f"{STREAM_AGENTS}.{agent_id}"
    cfg = replace(AGENT_CONSUMER_CONFIG, description=f"agent-{agent_id}")
    psub = await js.pull_subscribe(
        stream=STREAM_AGENTS,
        subject=f"{STREAM_AGENTS}.{agent_id}",
        config=cfg,
    )
    logger.info(f"Subscribed to {subject}")
    return psub


async def create_agent_parameter_consumer(
    js: JetStreamContext,
    agent_id: UUID,
    operator: OperatorJSON,
    parameter: OperatorParameter,
) -> JetStreamContext.PullSubscription:
    subject = f"{STREAM_PARAMETERS}.{operator.id}.{parameter.name}"
    cfg = replace(
        PARAMETER_CONSUMER_CONFIG,
        description=f"agent-{agent_id}-{operator.id}-{parameter.name}",
    )
    psub = await js.pull_subscribe(
        stream=STREAM_AGENTS,
        subject=subject,
        config=cfg,
    )
    logger.info(f"Subscribed to {subject}")
    return psub


async def create_operator_parameter_consumer(
    js: JetStreamContext,
    operator_id: UUID,
) -> JetStreamContext.PullSubscription:
    subject = f"{STREAM_PARAMETERS}.{operator_id}.>"
    cfg = replace(
        PARAMETER_CONSUMER_CONFIG,
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
    operator_id: UUID,
) -> JetStreamContext.PullSubscription:
    subject = f"{STREAM_OPERATORS}.{operator_id}"
    cfg = replace(
        PIPELINE_CONSUMER_CONFIG,
        description=f"operator-pipelines-{operator_id}",
    )
    psub = await js.pull_subscribe(
        stream=STREAM_OPERATORS,
        subject=subject,
        config=cfg,
    )
    logger.info(f"Subscribed to {subject}")
    return psub


async def create_orchestrator_pipeline_consumer(
    js: JetStreamContext,
    orchestrator_id: UUID,
) -> JetStreamContext.PullSubscription:
    subject = f"{SUBJECT_PIPELINES_RUN}"
    cfg = replace(
        PIPELINE_CONSUMER_CONFIG,
        description=f"orchestrator-{orchestrator_id}",
    )
    psub = await js.pull_subscribe(
        stream=STREAM_PIPELINES,
        subject=subject,
        config=cfg,
    )
    logger.info(f"Subscribed to {subject}")
    return psub


async def create_metrics_consumer(
    js: JetStreamContext,
) -> JetStreamContext.PullSubscription:
    subject = f"{STREAM_METRICS}.>"
    cfg = replace(
        METRICS_CONSUMER_CONFIG,
        description="metrics",
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
    subject = SUBJECT_SFAPI_JOBS_SUBMIT
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
