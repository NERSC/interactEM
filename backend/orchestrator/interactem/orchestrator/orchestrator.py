import asyncio
from uuid import UUID, uuid4

from nats.js import JetStreamContext
from pydantic import ValidationError

from interactem.core.constants import (
    AGENTS,
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
    get_val,
    publish_notification,
)
from interactem.core.nats.publish import publish_assignment
from interactem.core.pipeline import Pipeline

from .assign import PipelineAssigner
from .exceptions import (
    InvalidPipelineError,
)

logger = get_logger()

pipelines: dict[IdType, RuntimePipeline] = {}

task_refs: set[asyncio.Task] = set()


async def delete_pipeline_kv(js: JetStreamContext, pipeline_id: IdType):
    pipeline_bucket = await get_status_bucket(js)
    key = f"{PIPELINES}.{str(pipeline_id)}"  # TODO: use PipelineRunVal.key() instead
    await pipeline_bucket.delete(key)
    await pipeline_bucket.purge(key)


async def update_pipeline_kv(js: JetStreamContext, pipeline: RuntimePipeline):
    _pipeline = PipelineRunVal(id=pipeline.id, pipeline=pipeline)
    pipeline_bucket = await get_status_bucket(js)
    await pipeline_bucket.put(_pipeline.key(), _pipeline.model_dump_json().encode())


async def continuous_update_kv(js: JetStreamContext, interval: int = 10):
    while True:
        # Create a snapshot of pipeline values to avoid modification during iteration
        pipeline_snapshot = list(pipelines.values())
        for pipeline in pipeline_snapshot:
            await update_pipeline_kv(js, pipeline)
        logger.debug(f"Updated {len(pipeline_snapshot)} pipelines in KV store.")
        await asyncio.sleep(interval)


async def clean_up_old_pipelines(js: JetStreamContext, valid_pipeline: RuntimePipeline):
    bucket = await get_status_bucket(js)
    current_pipeline_keys = await get_keys(bucket, filters=[f"{PIPELINES}"])
    delete_tasks = []
    prefix = f"{PIPELINES}."
    for key in current_pipeline_keys:
        id = key.removeprefix(prefix)
        if id != str(valid_pipeline.id):
            try:
                uid = UUID(id)
                delete_tasks.append(delete_pipeline_kv(js, uid))
                logger.debug(f"Scheduled deletion for old pipeline id: {id}")
            except ValueError:
                logger.warning(f"Skipping deletion of non-UUID pipeline id: {id}")
    if delete_tasks:
        await asyncio.gather(*delete_tasks)
        logger.info(f"Deleted {len(delete_tasks)} old pipeline entries from KV store.")

    pipelines.clear()


async def handle_run_pipeline(event: PipelineRunEvent, js: JetStreamContext):
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
    bucket = await get_status_bucket(js)

    agent_keys = await get_keys(bucket, filters=[f"{AGENTS}"])

    agent_vals = await asyncio.gather(
        *[get_val(bucket, agent, AgentVal) for agent in agent_keys]
    )
    agent_vals = [agent_info for agent_info in agent_vals if agent_info]

    assigner = PipelineAssigner(agent_vals, pipeline)
    assignments = assigner.assign()

    tasks = [
        asyncio.create_task(publish_assignment(js, assignment))
        for assignment in assignments
    ]
    await asyncio.gather(*tasks)

    logger.info(f"Published {len(assignments)} assignments for pipeline {pipeline.id}.")
    runtime_pipeline = pipeline.to_runtime()
    tasks.clear()
    tasks.append(asyncio.create_task(clean_up_old_pipelines(js, runtime_pipeline)))
    tasks.append(asyncio.create_task(update_pipeline_kv(js, runtime_pipeline)))
    await asyncio.gather(*tasks)
    pipelines[runtime_pipeline.id] = runtime_pipeline
    logger.info(f"Updated KV store with pipeline {valid_pipeline.id}.")
    logger.info(f"Pipeline run event for {valid_pipeline.id} processed.")


async def handle_stop_pipeline_event(event: PipelineStopEvent, js: JetStreamContext):
    logger.info(f"Received pipeline stop event for deployment {event.deployment_id}...")
    deployment_id = event.deployment_id
    logger.info(f"Processing stop request for pipeline {deployment_id}")

    if deployment_id in pipelines:
        del pipelines[deployment_id]
        logger.debug(f"Removed pipeline {deployment_id} from local cache.")

    await delete_pipeline_kv(js, deployment_id)
    logger.info(f"Deleted pipeline {deployment_id} from KV store.")
    publish_notification(js=js, msg="Pipeline stopped", task_refs=task_refs)

    # Send stop command (empty assignment) to all agents
    status_bucket = await get_status_bucket(js)
    agent_keys = await get_keys(status_bucket, filters=[f"{AGENTS}"])

    if not agent_keys:
        logger.warning(
            f"No agents found to send stop command for pipeline {deployment_id}."
        )
        return

    agent_ids = [UUID(agent_key.removeprefix(f"{AGENTS}.")) for agent_key in agent_keys]

    # Create a runtime pipeline w/o operators for killing the pipelin

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
        for agent_id in agent_ids
    ]

    publish_tasks = [
        publish_assignment(js, assignment) for assignment in stop_assignments
    ]
    await asyncio.gather(*publish_tasks)

    logger.info(f"Pipeline stop event for {deployment_id} processed.")
