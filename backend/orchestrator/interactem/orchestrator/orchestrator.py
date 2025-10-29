import asyncio
from collections.abc import Callable
from functools import partial
from uuid import UUID, uuid4

from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
from pydantic import BaseModel, ValidationError

from interactem.core.constants import (
    AGENTS,
    NATS_API_KEY_HEADER,
    NATS_TIMEOUT_DEFAULT,
    PIPELINES,
    STREAM_DEPLOYMENTS,
    SUBJECT_PIPELINES_DEPLOYMENTS,
    SUBJECT_PIPELINES_DEPLOYMENTS_UPDATE,
)
from interactem.core.events.pipelines import (
    PipelineEvent,
    PipelineRunEvent,
    PipelineStopEvent,
    PipelineUpdateEvent,
)
from interactem.core.logger import get_logger
from interactem.core.models.base import IdType, PipelineDeploymentState
from interactem.core.models.canonical import CanonicalPipeline
from interactem.core.models.kvs import AgentVal, PipelineRunVal
from interactem.core.models.runtime import (
    PipelineAssignment,
    RuntimePipeline,
)
from interactem.core.nats import (
    consume_messages,
    get_keys,
    get_status_bucket,
    get_val,
    nc,
    publish_error,
    publish_notification,
)
from interactem.core.nats.consumers import (
    create_orchestrator_deployment_consumer,
)
from interactem.core.nats.publish import publish_assignment
from interactem.core.pipeline import Pipeline

from .assign import PipelineAssigner
from .config import cfg
from .exceptions import (
    CyclicDependenciesError,
    NetworkPreferenceError,
    NoAgentsError,
    UnassignableOperatorsError,
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


async def update_pipeline_status(
    js: JetStreamContext,
    event: PipelineRunEvent,
    state: PipelineDeploymentState,
):
    update_event = PipelineUpdateEvent(deployment_id=event.deployment_id, state=state)
    await js.publish(
        SUBJECT_PIPELINES_DEPLOYMENTS_UPDATE,
        stream=STREAM_DEPLOYMENTS,
        payload=update_event.model_dump_json().encode(),
        headers={NATS_API_KEY_HEADER: cfg.ORCHESTRATOR_API_KEY},
        timeout=NATS_TIMEOUT_DEFAULT,
    )


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


async def handle_run_pipeline(event: PipelineRunEvent, msg: NATSMsg, js: JetStreamContext):
    logger.info("Received pipeline run event...")

    try:
        valid_pipeline = CanonicalPipeline(
            id=event.canonical_id, revision_id=event.revision_id, **event.data
        )
    except ValidationError as e:
        logger.error(
            f"Invalid pipeline definition received for ID {str(event.canonical_id)}: {e}"
        )
        publish_error(
            js,
            "Pipeline cannot be assigned: Invalid pipeline definition.",
            task_refs=task_refs,
        )
        await msg.term()
        return

    logger.info(f"Validated pipeline: {valid_pipeline.id}")
    await msg.ack()
    pipeline = Pipeline.from_pipeline(
        valid_pipeline, runtime_pipeline_id=event.deployment_id
    )
    bucket = await get_status_bucket(js)

    agent_keys = await get_keys(bucket, filters=[f"{AGENTS}"])

    agent_vals = await asyncio.gather(
        *[get_val(bucket, agent, AgentVal) for agent in agent_keys]
    )
    agent_vals = [agent_info for agent_info in agent_vals if agent_info]

    try:
        assigner = PipelineAssigner(agent_vals, pipeline)
    except CyclicDependenciesError as e:
        logger.exception(
            f"Pipeline {pipeline.id} cannot be assigned due to graph errors: {e}."
        )
        publish_error(
            js,
            "Pipeline cannot be assigned: cyclic dependencies in pipeline.",
            task_refs=task_refs,
        )
        await update_pipeline_status(js, event, PipelineDeploymentState.FAILED_TO_START)

        return
    except NoAgentsError:
        logger.exception(
            f"Pipeline {pipeline.id} cannot be assigned: no agents available."
        )
        publish_error(
            js,
            "Pipeline cannot be assigned: no agents available.",
            task_refs=task_refs,
        )
        await update_pipeline_status(js, event, PipelineDeploymentState.FAILED_TO_START)
        return

    try:
        assignments = assigner.assign()
    except UnassignableOperatorsError:
        logger.exception(f"Pipeline {pipeline.id} has unassignable operators.")
        publish_error(
            js,
            "Pipeline cannot be assigned: unassignable operators.",
            task_refs=task_refs,
        )
        await update_pipeline_status(js, event, PipelineDeploymentState.FAILED_TO_START)
        return
    except NetworkPreferenceError:
        logger.exception(f"Pipeline {pipeline.id} has network preference violations.")
        publish_error(
            js,
            "Pipeline cannot be assigned: network preference violations.",
            task_refs=task_refs,
        )
        await update_pipeline_status(js, event, PipelineDeploymentState.FAILED_TO_START)
        return

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
    tasks.append(asyncio.create_task(
        update_pipeline_status(js, event, PipelineDeploymentState.RUNNING)
    ))
    await asyncio.gather(*tasks)
    pipelines[runtime_pipeline.id] = runtime_pipeline
    logger.info(f"Updated KV store with pipeline {valid_pipeline.id}.")
    logger.info(f"Pipeline run event for {valid_pipeline.id} processed.")


async def handle_stop_pipeline_event(event: PipelineStopEvent, msg: NATSMsg, js: JetStreamContext):
    logger.info(f"Received pipeline stop event for deployment {event.deployment_id}...")
    await msg.ack()

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


async def handle_deployment_event(msg: NATSMsg, js: JetStreamContext):
    try:
        event = PipelineEvent.model_validate_json(msg.data)
    except ValidationError as e:
        logger.error(f"Invalid deployment event message: {e}")
        await msg.term()
        return

    func_map: dict[type[BaseModel], Callable] = {
        PipelineRunEvent: handle_run_pipeline,
        PipelineStopEvent: handle_stop_pipeline_event,
    }

    handler = func_map.get(type(event.root))
    if handler:
        await handler(event.root, msg, js)
    elif isinstance(event.root, PipelineUpdateEvent):
        logger.debug(f"Ignoring PipelineUpdateEvent for deployment {event.root.deployment_id}")
        await msg.ack()
    else:
        raise NotImplementedError(f"No handler for event type {type(event.root)}")

async def main():
    instance_id: UUID = uuid4()
    nats_client: NATSClient = await nc(
        [str(cfg.NATS_SERVER_URL)],
        f"orchestrator-{instance_id}",
    )
    js: JetStreamContext = nats_client.jetstream()

    logger.info(f"Orchestrator instance {instance_id} starting...")

    try:
        logger.info("NATS buckets and streams initialized/verified.")

        create_deployment_psub = partial(
            create_orchestrator_deployment_consumer, js, instance_id, SUBJECT_PIPELINES_DEPLOYMENTS
        )
        deployment_psub = await create_deployment_psub()
        logger.info("Deployment event consumer created.")

        update_task = asyncio.create_task(continuous_update_kv(js))
        task_refs.add(update_task)

        deployment_consumer_task = asyncio.create_task(
            consume_messages(
                deployment_psub,
                handle_deployment_event,
                js,
                create_consumer=create_deployment_psub,
            )
        )
        task_refs.add(deployment_consumer_task)

        logger.info(
            f"Orchestrator instance {instance_id} running. Waiting for events..."
        )
        await asyncio.gather(deployment_consumer_task, update_task)

    finally:
        if nats_client and nats_client.is_connected:
            await nats_client.close()

        for task in task_refs:
            task.cancel()
        await asyncio.gather(*task_refs, return_exceptions=True)
        logger.info(f"Orchestrator instance {instance_id} shut down.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Orchestrator stopped by user.")
    except Exception:
        logger.exception("Unhandled exception in orchestrator.")
