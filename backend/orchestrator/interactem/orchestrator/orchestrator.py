import asyncio
from itertools import cycle
from uuid import UUID, uuid4

import nats
import nats.js
import nats.js.errors
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
from pydantic import ValidationError

from interactem.core.constants import (
    BUCKET_AGENTS,
    BUCKET_AGENTS_TTL,
    BUCKET_PIPELINES,
    BUCKET_PIPELINES_TTL,
    STREAM_AGENTS,
)
from interactem.core.events.pipelines import PipelineRunEvent
from interactem.core.logger import get_logger
from interactem.core.models.agent import AgentVal
from interactem.core.models.base import IdType
from interactem.core.models.pipeline import PipelineAssignment, PipelineJSON
from interactem.core.nats import (
    consume_messages,
    create_bucket_if_doesnt_exist,
    create_or_update_stream,
    get_agents_bucket,
    get_keys,
    get_pipelines_bucket,
    get_val,
)
from interactem.core.nats.config import (
    AGENTS_STREAM_CONFIG,
    OPERATORS_STREAM_CONFIG,
    PIPELINES_STREAM_CONFIG,
)
from interactem.core.nats.consumers import create_orchestrator_pipeline_consumer
from interactem.core.pipeline import OperatorJSON, Pipeline

from .config import cfg

logger = get_logger()

pipelines = {}


async def publish_assignment(js: JetStreamContext, assignment: PipelineAssignment):
    await js.publish(
        f"{STREAM_AGENTS}.{assignment.agent_id}",
        stream=f"{STREAM_AGENTS}",
        payload=assignment.model_dump_json().encode(),
    )


async def delete_pipeline_kv(js: JetStreamContext, pipeline_id: IdType):
    pipeline_bucket = await get_pipelines_bucket(js)
    await pipeline_bucket.delete(str(pipeline_id))


async def update_pipeline_kv(js: JetStreamContext, pipeline: PipelineJSON):
    pipeline_bucket = await get_pipelines_bucket(js)
    await pipeline_bucket.put(str(pipeline.id), pipeline.model_dump_json().encode())


async def continuous_update_kv(js: JetStreamContext, interval: int = 10):
    while True:
        for pipeline in pipelines.values():
            await update_pipeline_kv(js, pipeline)
        await asyncio.sleep(interval)


def assign_pipeline_to_agents(agent_infos: list[AgentVal], pipeline: Pipeline):
    # TODO: this is ugly
    # Group agents by machine name
    agents_on_machines: dict[str, list[AgentVal]] = {}
    agents_without_machines: list[AgentVal] = []
    for agent_info in agent_infos:
        if agent_info.machine_name:
            if agent_info.machine_name not in agents_on_machines:
                agents_on_machines[agent_info.machine_name] = []
            agents_on_machines[agent_info.machine_name].append(agent_info)
        else:
            agents_without_machines.append(agent_info)

    # Group operators by machine name
    operators_on_machines: dict[str, list[OperatorJSON]] = {}
    operators_without_machines: list[OperatorJSON] = []
    for operator in pipeline.operators.values():
        if operator.machine_name:
            if operator.machine_name not in operators_on_machines:
                operators_on_machines[operator.machine_name] = []
            operators_on_machines[operator.machine_name].append(operator)
        else:
            operators_without_machines.append(operator)

    # Assign operators with machine names to agents with corresponding machine names using round-robin
    assignments: dict[IdType, list[OperatorJSON]] = {}
    for machine_name, operators in operators_on_machines.items():
        agents_on_this_machine = agents_on_machines.get(machine_name, None)
        if not agents_on_this_machine:
            raise Exception(f"No agents available for machine {machine_name}")

        agent_cycle = cycle(agents_on_this_machine)
        for operator in operators:
            agent = next(agent_cycle)
            agent_id = agent.uri.id
            if agent_id not in assignments:
                assignments[agent_id] = []
            assignments[agent_id].append(operator)

    # Assign operators without machine names to agents without machine names using round-robin
    if operators_without_machines:
        if not agents_without_machines:
            raise Exception("No agents available for operators without machine names")

        agent_cycle = cycle(agents_without_machines)
        for operator in operators_without_machines:
            agent = next(agent_cycle)
            agent_id = agent.uri.id
            if agent_id not in assignments:
                assignments[agent_id] = []
            assignments[agent_id].append(operator)

    pipeline_assignments: list[PipelineAssignment] = []
    for agent_id, operators in assignments.items():
        pipeline_assignment = PipelineAssignment(
            agent_id=agent_id,
            operators_assigned=[op.id for op in operators],
            pipeline=pipeline.to_json(),
        )
        pipeline_assignments.append(pipeline_assignment)

    formatted_assignments = "\n".join(
        f"Agent {assignment.agent_id}:\n"
        + "\n".join(
            f"  Operator {op_id} on machine {next(op.machine_name for op in assignment.pipeline.operators if op.id == op_id)}"
            for op_id in assignment.operators_assigned
        )
        for assignment in pipeline_assignments
    )

    logger.info(f"Final assignments:\n{formatted_assignments}")

    return pipeline_assignments


async def handle_run_pipeline(msg: NATSMsg, js: JetStreamContext):
    logger.info("Received pipeline run event...")
    await msg.ack()

    try:
        event = PipelineRunEvent.model_validate_json(msg.data)
    except ValidationError:
        logger.error("Invalid message")
        return

    try:
        valid_pipeline = PipelineJSON(id=event.id, **event.data)
    except ValidationError as e:
        logger.error(f"Invalid pipeline: {e}")
        return
    logger.info(f"Validated pipeline: {valid_pipeline.id}")
    pipeline = Pipeline.from_pipeline(valid_pipeline)
    bucket = await get_agents_bucket(js)

    agent_keys = await get_keys(bucket)
    if len(agent_keys) == 0:
        logger.info("No agents available to run pipeline.")
        # TODO: publish event to send message back to API that says this won't work
        return

    agent_vals = await asyncio.gather(
        *[get_val(bucket, agent, AgentVal) for agent in agent_keys]
    )
    agent_vals = [agent_info for agent_info in agent_vals if agent_info]

    try:
        assignments = assign_pipeline_to_agents(agent_vals, pipeline)
    except Exception as e:
        logger.error(f"Failed to assign pipeline to agents:  {e}")
        return
    await asyncio.gather(
        *[publish_assignment(js, assignment) for assignment in assignments]
    )

    logger.info("Pipeline assigned to agents.")
    current_pipelines = await get_keys(await get_pipelines_bucket(js))
    for pipeline_id in current_pipelines:
        if pipeline_id != valid_pipeline.id:
            uid = UUID(pipeline_id)
            await delete_pipeline_kv(js, uid)
    await update_pipeline_kv(js, valid_pipeline)
    pipelines[valid_pipeline.id] = valid_pipeline
    logger.info("Pipeline run event processed.")


async def main():
    id: UUID = uuid4()
    nc: NATSClient = await nats.connect(
        servers=[str(cfg.NATS_SERVER_URL)], name=f"orchestrator-{id}"
    )
    js: JetStreamContext = nc.jetstream()

    logger.info("Orchestrator is running...")

    startup_tasks = []
    startup_tasks.append(
        create_bucket_if_doesnt_exist(js, BUCKET_AGENTS, BUCKET_AGENTS_TTL),
    )
    startup_tasks.append(
        create_bucket_if_doesnt_exist(js, BUCKET_PIPELINES, BUCKET_PIPELINES_TTL),
    )

    startup_tasks.append(create_or_update_stream(AGENTS_STREAM_CONFIG, js))
    startup_tasks.append(create_or_update_stream(OPERATORS_STREAM_CONFIG, js))
    startup_tasks.append(create_or_update_stream(PIPELINES_STREAM_CONFIG, js))

    await asyncio.gather(*startup_tasks)

    pipeline_run_psub = await create_orchestrator_pipeline_consumer(js, id)

    asyncio.create_task(continuous_update_kv(js))

    await asyncio.gather(
        consume_messages(pipeline_run_psub, handle_run_pipeline, js),
    )

    while True:
        await asyncio.sleep(1)
