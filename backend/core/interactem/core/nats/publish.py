from faststream.nats.broker import NatsBroker
from faststream.nats.publisher.usecase import LogicPublisher
from nats.js import JetStreamContext

from interactem.core.models.kvs import CanonicalOperatorID
from interactem.core.models.runtime import RuntimeOperatorParameter

from ..constants import (
    NATS_API_KEY_HEADER,
    NATS_TIMEOUT_DEFAULT,
    STREAM_DEPLOYMENTS,
    STREAM_IMAGES,
    STREAM_PARAMETERS,
    STREAM_TABLES,
    SUBJECT_AGENTS_DEPLOYMENTS,
    SUBJECT_NOTIFICATIONS_ERRORS,
    SUBJECT_NOTIFICATIONS_INFO,
    SUBJECT_OPERATORS_DEPLOYMENTS,
    SUBJECT_OPERATORS_PARAMETERS,
    SUBJECT_PIPELINES_DEPLOYMENTS_UPDATE,
    SUBJECT_PIPELINES_METRICS,
)
from ..models.base import IdType
from ..models.messages import (
    TrackingMetadatas,
)
from ..models.runtime import (
    PipelineAssignment,
    RuntimeOperatorID,
    RuntimeOperatorParameterAck,
)
from ..nats.streams import (
    DEPLOYMENTS_JSTREAM,
    NOTIFICATIONS_JSTREAM,
    PARAMETERS_JSTREAM,
)
from ..pipeline import Pipeline as PipelineGraph


async def publish_pipeline_metrics(
    js: JetStreamContext,
    tracking: TrackingMetadatas,
):
    """Used to send out the tracking information."""
    await js.publish(
        SUBJECT_PIPELINES_METRICS,
        tracking.model_dump_json().encode(),
        timeout=NATS_TIMEOUT_DEFAULT,
    )


async def publish_operator_parameter_ack(
    js: JetStreamContext,
    # TODO: on the way back, we should use the runtime ID instead
    # of canonical, that way we can ensure (somewhere else) that the
    # parameters are set on all instances of the operator
    id: CanonicalOperatorID,
    parameter: RuntimeOperatorParameter,
):
    event = RuntimeOperatorParameterAck(
        canonical_operator_id=id, name=parameter.name, value=parameter.value
    )
    await js.publish(
        subject=f"{SUBJECT_OPERATORS_PARAMETERS}.{id}.{parameter.name}",
        stream=STREAM_PARAMETERS,
        payload=event.model_dump_json().encode(),
        timeout=NATS_TIMEOUT_DEFAULT,
    )


async def publish_assignment(js: JetStreamContext, assignment: PipelineAssignment):
    await js.publish(
        f"{SUBJECT_AGENTS_DEPLOYMENTS}.{assignment.agent_id}",
        stream=STREAM_DEPLOYMENTS,
        payload=assignment.model_dump_json().encode(),
        timeout=NATS_TIMEOUT_DEFAULT,
    )

async def publish_image(
    js: JetStreamContext,
    image_data: bytes,
    # TODO: come back if we create a "runtime" display in the frontend
    canonical_operator_id: CanonicalOperatorID,
):
    await js.publish(
        subject=f"{STREAM_IMAGES}.{canonical_operator_id}",
        payload=image_data,
        timeout=NATS_TIMEOUT_DEFAULT,
    )


async def publish_table_data(
    js: JetStreamContext,
    table_data_json: bytes,
    operator_id: CanonicalOperatorID,
):
    await js.publish(
        subject=f"{STREAM_TABLES}.{operator_id}",
        payload=table_data_json,
        timeout=NATS_TIMEOUT_DEFAULT,
    )

async def publish_pipeline_to_operators(
    broker: NatsBroker,
    pipeline: PipelineGraph,
    operator_id: RuntimeOperatorID,
):
    await broker.publish(
        subject=f"{SUBJECT_OPERATORS_DEPLOYMENTS}.{operator_id}",
        message=pipeline.to_runtime().model_dump_json(),
        stream=STREAM_DEPLOYMENTS,
        timeout=NATS_TIMEOUT_DEFAULT,
    )

def create_agent_mount_publisher(
    broker: NatsBroker,
    canonical_operator_id: CanonicalOperatorID,
    parameter_name: str,
) -> LogicPublisher:
    subject = f"{SUBJECT_OPERATORS_PARAMETERS}.{canonical_operator_id}.{parameter_name}"
    return broker.publisher(
        stream=PARAMETERS_JSTREAM,
        subject=subject,
        timeout=NATS_TIMEOUT_DEFAULT,
    )

async def publish_agent_mount_parameter_ack(
    publisher: LogicPublisher,
    canonical_operator_id: CanonicalOperatorID,
    parameter: RuntimeOperatorParameter,
):
    """Publish mount parameter acknowledgment from agent"""
    event = RuntimeOperatorParameterAck(
        canonical_operator_id=canonical_operator_id,
        name=parameter.name,
        value=parameter.value,
    )
    await publisher.publish(
        message=event.model_dump_json().encode(),
        timeout=NATS_TIMEOUT_DEFAULT,
    )


def create_error_publisher(
    broker: NatsBroker,
    id: IdType,
) -> LogicPublisher:
    subject = f"{SUBJECT_NOTIFICATIONS_ERRORS}.{id}"
    return broker.publisher(
        stream=NOTIFICATIONS_JSTREAM,
        subject=subject,
        timeout=NATS_TIMEOUT_DEFAULT,
    )


def create_info_publisher(
    broker: NatsBroker,
    id: IdType,
) -> LogicPublisher:
    subject = f"{SUBJECT_NOTIFICATIONS_INFO}.{id}"
    return broker.publisher(
        stream=NOTIFICATIONS_JSTREAM,
        subject=subject,
        timeout=NATS_TIMEOUT_DEFAULT,
    )


def create_deployment_status_publisher(
    broker: NatsBroker, api_key: str
) -> LogicPublisher:
    return broker.publisher(
        stream=DEPLOYMENTS_JSTREAM,
        subject=f"{SUBJECT_PIPELINES_DEPLOYMENTS_UPDATE}",
        headers={NATS_API_KEY_HEADER: api_key},
        timeout=NATS_TIMEOUT_DEFAULT,
    )
