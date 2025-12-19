from dataclasses import replace
from uuid import UUID

from nats.errors import Error as GenericNatsError
from nats.js import JetStreamContext
from nats.js.api import (
    ConsumerConfig,
    DeliverPolicy,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
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
    SUBJECT_SFAPI_JOBS,
)
from interactem.core.logger import get_logger
from interactem.core.models.canonical import CanonicalOperatorID
from interactem.core.models.runtime import RuntimeOperatorID

logger = get_logger()

AGENT_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.NEW,
    inactive_threshold=30,
)

SFAPI_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.NEW,
    inactive_threshold=30,
)

ORCHESTRATOR_DEPLOYMENTS_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.NEW, durable_name="orchestrator-deployments-consumer"
)

OPERATOR_PIPELINE_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.LAST_PER_SUBJECT,
)

PIPELINE_UPDATE_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.NEW,
)

METRICS_CONSUMER_CONFIG = ConsumerConfig(
    deliver_policy=DeliverPolicy.LAST_PER_SUBJECT,
)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
    retry=retry_if_exception_type(GenericNatsError),
    reraise=True,
)
async def create_pull_sub(
    js: JetStreamContext, stream: str, subject: str, cfg: ConsumerConfig
) -> JetStreamContext.PullSubscription:
    psub = await js.pull_subscribe(
        stream=stream,
        subject=subject,
        config=cfg,
    )
    logger.info(f"Subscribed to {subject}")
    return psub


async def create_agent_consumer(
    js: JetStreamContext,
    agent_id: UUID,
) -> JetStreamContext.PullSubscription:
    subject = f"{SUBJECT_AGENTS_DEPLOYMENTS}.{agent_id}"
    cfg = replace(AGENT_CONSUMER_CONFIG, description=f"agent-{agent_id}")
    psub = await create_pull_sub(js, STREAM_DEPLOYMENTS, subject, cfg)
    return psub


async def create_agent_mount_consumer(
    js: JetStreamContext,
    agent_id: UUID,
    canonical_operator_id: CanonicalOperatorID,
    parameter_name: str,
) -> JetStreamContext.PullSubscription:
    subject = (
        f"{SUBJECT_OPERATORS_PARAMETERS_UPDATE}.{canonical_operator_id}.{parameter_name}"
    )
    cfg = replace(
        PIPELINE_UPDATE_CONSUMER_CONFIG,
        description=f"agent-{agent_id}-{canonical_operator_id}-{parameter_name}",
    )
    psub = await create_pull_sub(js, STREAM_PARAMETERS, subject, cfg)
    return psub


async def create_operator_parameter_consumer(
    js: JetStreamContext,
    operator_id: CanonicalOperatorID,
) -> JetStreamContext.PullSubscription:
    subject = f"{SUBJECT_OPERATORS_PARAMETERS_UPDATE}.{operator_id}.>"
    cfg = replace(
        PIPELINE_UPDATE_CONSUMER_CONFIG,
        description=f"operator-{operator_id}",
    )
    psub = await create_pull_sub(js, STREAM_PARAMETERS, subject, cfg)
    return psub


async def create_operator_pipeline_consumer(
    js: JetStreamContext,
    operator_id: RuntimeOperatorID,
) -> JetStreamContext.PullSubscription:
    subject = f"{SUBJECT_OPERATORS_DEPLOYMENTS}.{operator_id}"
    cfg = replace(
        OPERATOR_PIPELINE_CONSUMER_CONFIG,
        description=f"operator-pipelines-{operator_id}",
    )
    psub = await create_pull_sub(js, STREAM_DEPLOYMENTS, subject, cfg)
    return psub


async def create_metrics_consumer(
    js: JetStreamContext,
) -> JetStreamContext.PullSubscription:
    subject = SUBJECT_METRICS_ALL
    cfg = replace(
        METRICS_CONSUMER_CONFIG,
        description="metrics-microservice-consumer",
    )
    psub = await create_pull_sub(js, STREAM_METRICS, subject, cfg)
    return psub


async def create_sfapi_submit_consumer(
    js: JetStreamContext,
) -> JetStreamContext.PullSubscription:
    subject = SUBJECT_SFAPI_JOBS
    cfg = replace(
        SFAPI_CONSUMER_CONFIG,
        description="sfapi_submit_consumer",
    )
    psub = await create_pull_sub(js, STREAM_SFAPI, subject, cfg)
    return psub
