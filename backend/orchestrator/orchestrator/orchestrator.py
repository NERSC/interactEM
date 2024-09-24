import asyncio
from collections.abc import Awaitable, Callable
from itertools import cycle
from uuid import uuid4

import nats
import nats.js
import nats.js.errors
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
from nats.js.api import ConsumerConfig, DeliverPolicy, StreamConfig
from nats.js.errors import BadRequestError, KeyNotFoundError, NoKeysError
from nats.js.kv import KeyValue
from pydantic import ValidationError

from core.constants import (
    BUCKET_AGENTS,
    BUCKET_AGENTS_TTL,
    STREAM_AGENTS,
    STREAM_OPERATORS,
    SUBJECT_PIPELINES_RUN,
)
from core.events.pipelines import PipelineRunEvent
from core.logger import get_logger
from core.models.agent import AgentVal
from core.models.base import IdType
from core.models.pipeline import PipelineAssignment, PipelineJSON
from core.pipeline import OperatorJSON, Pipeline

from .config import cfg

logger = get_logger("orchestrator", "DEBUG")


async def publish_assignment(js: JetStreamContext, assignment: PipelineAssignment):
    await js.publish(
        f"{STREAM_AGENTS}.{assignment.agent_id}",
        stream=f"{STREAM_AGENTS}",
        payload=assignment.model_dump_json().encode(),
    )


def assign_pipeline_to_agents(agent_infos: list[AgentVal], pipeline: Pipeline):
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
    # TODO: use try/except here
    valid_pipeline = PipelineJSON(id=event.id, **event.data)
    logger.info(f"Validated pipeline: {valid_pipeline.id}")
    pipeline = Pipeline.from_pipeline(valid_pipeline)

    agents = await get_agents(js)
    if len(agents) == 0:
        logger.info("No agents available to run pipeline.")
        # TODO: publish event to send message back to API that says this won't work
        return

    agent_infos = await asyncio.gather(*[get_agent_info(js, agent) for agent in agents])
    agent_infos = [agent_info for agent_info in agent_infos if agent_info]

    try:
        assignments = assign_pipeline_to_agents(agent_infos, pipeline)
    except Exception as e:
        logger.error(f"Failed to assign pipeline to agents:  {e}")
        return

    await asyncio.gather(
        *[publish_assignment(js, assignment) for assignment in assignments]
    )

    logger.info("Pipeline run event processed.")


async def consume_messages(
    psub: JetStreamContext.PullSubscription,
    handler: Callable[[NATSMsg, JetStreamContext], Awaitable],
    js: JetStreamContext,
):
    while True:
        msgs = await psub.fetch(1, timeout=None)
        for msg in msgs:
            await handler(msg, js)


async def get_current_num_agents(js: JetStreamContext):
    try:
        bucket = await js.key_value(BUCKET_AGENTS)
    except nats.js.errors.BucketNotFoundError:
        bucket_cfg = nats.js.api.KeyValueConfig(
            bucket=BUCKET_AGENTS, ttl=BUCKET_AGENTS_TTL
        )
        bucket = await js.create_key_value(config=bucket_cfg)
    try:
        num_agents = len(await bucket.keys())
    except NoKeysError:
        return 0
    return num_agents


async def get_agents(js: JetStreamContext) -> list[str]:
    bucket = await js.key_value(BUCKET_AGENTS)
    try:
        agents = await bucket.keys()
    except NoKeysError:
        return []
    return agents


async def get_agent_info(js: JetStreamContext, agent_id: str) -> AgentVal | None:
    bucket = await js.key_value(BUCKET_AGENTS)
    try:
        entry = await bucket.get(agent_id)
        if not entry.value:
            return
        return AgentVal.model_validate_json(entry.value)
    except KeyNotFoundError:
        return


async def create_bucket_if_doesnt_exist(
    js: JetStreamContext, bucket_name: str, ttl: int
) -> KeyValue:
    try:
        kv = await js.key_value(bucket_name)
    except nats.js.errors.BucketNotFoundError:
        bucket_cfg = nats.js.api.KeyValueConfig(bucket=bucket_name, ttl=ttl)
        kv = await js.create_key_value(config=bucket_cfg)
    return kv


async def main():
    id: str = str(uuid4())
    nc: NATSClient = await nats.connect(
        servers=[str(cfg.NATS_SERVER_URL)], name=f"orchestrator-{id}"
    )
    js: JetStreamContext = nc.jetstream()

    logger.info("Orchestrator is running...")
    consumer_cfg = ConsumerConfig(
        description=f"orchestrator-{id}", deliver_policy=DeliverPolicy.LAST_PER_SUBJECT
    )
    pipeline_run_psub = await js.pull_subscribe(
        subject=SUBJECT_PIPELINES_RUN, config=consumer_cfg
    )

    await create_bucket_if_doesnt_exist(js, BUCKET_AGENTS, BUCKET_AGENTS_TTL)

    agent_stream_cfg = StreamConfig(
        name=STREAM_AGENTS,
        description="A stream for messages to the agents.",
        subjects=[f"{STREAM_AGENTS}.>"],
    )

    # TODO: make this a util
    try:
        agent_stream_info = await js.add_stream(config=agent_stream_cfg)
    except BadRequestError as e:
        if e.err_code == 10058:  # Stream already exists
            agent_stream_info = await js.update_stream(config=agent_stream_cfg)
        else:
            raise

    logger.info(f"Created or updated agents stream: {agent_stream_info}")

    operators_stream_cfg = StreamConfig(
        name=STREAM_OPERATORS,
        description="A stream for messages for operators.",
        subjects=[f"{STREAM_OPERATORS}.>"],
    )

    # TODO: make this a util
    try:
        operators_stream_info = await js.add_stream(config=operators_stream_cfg)
    except BadRequestError as e:
        if e.err_code == 10058:  # Stream already exists
            operators_stream_info = await js.update_stream(config=operators_stream_cfg)
        else:
            raise

    logger.info(f"Created or updated operators stream: {operators_stream_info}")

    await asyncio.gather(
        consume_messages(pipeline_run_psub, handle_run_pipeline, js),
    )

    while True:
        await asyncio.sleep(1)
