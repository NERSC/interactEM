from uuid import UUID, uuid4

import anyio
from nats.js import JetStreamContext
from pydantic import ValidationError

from interactem.core.constants import (
    PIPELINES,
)
from interactem.core.events.pipelines import (
    PipelineRunEvent,
    PipelineStopEvent,
)
from interactem.core.logger import get_logger
from interactem.core.models.base import IdType
from interactem.core.models.canonical import CanonicalPipeline
from interactem.core.models.kvs import AgentVal, PipelineRunVal
from interactem.core.models.runtime import (
    PipelineAssignment,
    RuntimePipeline,
)
from interactem.core.nats import (
    get_keys,
    get_status_bucket,
)
from interactem.core.nats.publish import publish_assignment
from interactem.core.pipeline import Pipeline

from .assign import PipelineAssigner
from .exceptions import InvalidPipelineError

logger = get_logger()
    _pipeline = PipelineRunVal(id=pipeline.id, pipeline=pipeline)
async def continuous_update_kv(
            deployments_snapshot = list(state.values())
                await update_pipeline_kv(js, pipeline)
            await anyio.sleep(interval)


    bucket = await get_status_bucket(js, create=False)
    current_pipeline_keys = await get_keys(bucket, filters=[f"{PIPELINES}"])

async def handle_run_pipeline(
    event: PipelineRunEvent,
    js: JetStreamContext,
    deployments: dict[IdType, RuntimePipeline],
    agents: dict[str, AgentVal],
):
    try:
        valid_pipeline = CanonicalPipeline(
            id=event.canonical_id, revision_id=event.revision_id, **event.data
        )
    except ValidationError as e:
        logger.error(
            f"Invalid pipeline definition received for ID {str(event.canonical_id)}: {e}"
        )
        raise InvalidPipelineError(
            f"Pipeline {str(event.canonical_id)} is invalid and cannot be processed."
        ) from e

    logger.info(f"Validated pipeline: {valid_pipeline.id}")
    pipeline = Pipeline.from_pipeline(
        valid_pipeline, runtime_pipeline_id=event.deployment_id
    )
    agent_vals = list(agents.values())

    assigner = PipelineAssigner(agent_vals, pipeline)
    assignments = assigner.assign()

    async with anyio.create_task_group() as tg:
        for assignment in assignments:
            tg.start_soon(publish_assignment, js, assignment)

    logger.info(f"Published {len(assignments)} assignments for pipeline {pipeline.id}.")

    runtime_pipeline = pipeline.to_runtime()

    async with anyio.create_task_group() as tg:
        tg.start_soon(clean_up_old_pipelines, js, runtime_pipeline)
        tg.start_soon(update_pipeline_kv, js, runtime_pipeline)

    deployments[runtime_pipeline.id] = runtime_pipeline
    logger.info(f"Pipeline {valid_pipeline.id} run event processed.")


async def handle_stop_pipeline_event(
    event: PipelineStopEvent,
    js: JetStreamContext,
    deployments: dict[IdType, RuntimePipeline],
    agents: dict[IdType, AgentVal],
):
    deployment_id = event.deployment_id
    logger.info(f"Processing stop request for pipeline {deployment_id}")

    deployments.pop(deployment_id, None)
    await delete_pipeline_kv(js, deployment_id)
    logger.info(f"Deleted pipeline {deployment_id} from KV store.")

    # TODO: for now, we use a blank pipeline to stop things
    # we should probably have a more explicit "stop" pipeline message
    canonical_pipeline = CanonicalPipeline(
        id=uuid4(), revision_id=0, operators=[], edges=[]
    )

    # Convert to runtime pipeline for assignment
    runtime_pipeline = Pipeline.from_pipeline(
        canonical_pipeline, runtime_pipeline_id=deployment_id
    ).to_runtime()

    stop_assignments = [
        PipelineAssignment(
            agent_id=agent_id,
            operators_assigned=[],
            pipeline=runtime_pipeline,
        )
        for agent_id in list(agents.keys())
    ]

    async with anyio.create_task_group() as tg:
        for assignment in stop_assignments:
            tg.start_soon(publish_assignment, js, assignment)

    logger.info(f"Pipeline stop event for {deployment_id} processed.")
