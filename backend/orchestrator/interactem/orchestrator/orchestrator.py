import asyncio
from itertools import cycle
from uuid import UUID, uuid4

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
    nc,
    publish_error,
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

task_refs: set[asyncio.Task] = set()


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


def assign_pipeline_to_agents(
    js: JetStreamContext, agent_infos: list[AgentVal], pipeline: Pipeline
):
    """
    Assign pipeline operators to agents based on tag matching.

    The matching algorithm prioritizes:
    1. Agents with matching tags
    2. Agents with the most matching tags
    3. Load balancing among qualified agents
    """
    assignments: dict[IdType, list[OperatorJSON]] = {}
    unassigned_operators = list(pipeline.operators.values())
    # Keep track of operators that couldn't be assigned due to tag mismatch
    unassignable_operators = []

    def find_matching_agents(operator: OperatorJSON):
        """Helper function to find agents matching an operator's tags"""
        op_tag_values = {tag.value for tag in operator.tags}

        # If operator has no tags, it can go anywhere
        if not op_tag_values:
            return [(agent, 0) for agent in agent_infos]

        matching_agents = []
        for agent in agent_infos:
            agent_tag_values = set(agent.tags)

            # Check for any matching tags
            common_tags = op_tag_values.intersection(agent_tag_values)
            if not common_tags:
                continue

            # Count matching tags for ranking
            match_count = len(common_tags)
            matching_agents.append((agent, match_count))

        return matching_agents

    def assign_to_best_agent(
        matching_agents: list[tuple[AgentVal, int]], operator: OperatorJSON
    ):
        """Helper to assign operator to the best agent from candidates"""
        if not matching_agents:
            return False

        # Sort by number of matching tags (highest first)
        matching_agents.sort(key=lambda x: x[1], reverse=True)

        # Get all agents with the highest match score
        best_score = matching_agents[0][1]
        best_agents = [a for a, score in matching_agents if score == best_score]

        # Choose agent with the lowest current load
        best_agent = min(best_agents, key=lambda a: len(assignments.get(a.uri.id, [])))

        # Assign the operator
        agent_id = best_agent.uri.id
        if agent_id not in assignments:
            assignments[agent_id] = []

        assignments[agent_id].append(operator)
        unassigned_operators.remove(operator)
        return True

    # Main assignment pass: match by tags
    for operator in list(unassigned_operators):
        matching_agents = find_matching_agents(operator)
        success = assign_to_best_agent(matching_agents, operator)

        # If we couldn't assign this operator, it has tags that don't match any agent
        if not success and operator.tags:  # Only log as unassignable if it has tags
            unassignable_operators.append(operator)
            _msg = f"Operator {operator.id} has tags {[tag.value for tag in operator.tags]} that don't match any agent"
            logger.error(_msg)
            publish_error(js, _msg, task_refs)

    # Final pass: round-robin assign any remaining operators (those without tags)
    remaining_operators = [
        op for op in unassigned_operators if op not in unassignable_operators
    ]
    if remaining_operators:
        # Sort agents by current load (number of assigned operators)
        sorted_agents = sorted(
            agent_infos, key=lambda a: len(assignments.get(a.uri.id, []))
        )
        agent_cycle = cycle(sorted_agents)

        for operator in remaining_operators:
            agent = next(agent_cycle)
            agent_id = agent.uri.id
            if agent_id not in assignments:
                assignments[agent_id] = []

            assignments[agent_id].append(operator)
            unassigned_operators.remove(operator)

    # Log any operators that couldn't be assigned
    for operator in unassigned_operators:
        _msg = f"Failed to assign operator {operator.id} to any agent"
        logger.error(_msg)
        publish_error(js, _msg, task_refs)

    # Create pipeline assignments
    pipeline_assignments: list[PipelineAssignment] = []
    for agent_id, operators in assignments.items():
        pipeline_assignment = PipelineAssignment(
            agent_id=agent_id,
            operators_assigned=[op.id for op in operators],
            pipeline=pipeline.to_json(),
        )
        pipeline_assignments.append(pipeline_assignment)

    # Generate human-readable assignment log
    formatted_assignments = "\n".join(
        f"Agent {assignment.agent_id} (tags: {next((a.tags for a in agent_infos if a.uri.id == assignment.agent_id), [])}):\n"
        + "\n".join(
            f"  Operator {op_id} (tags: {[tag.value for tag in next((op.tags for op in assignment.pipeline.operators if op.id == op_id), [])]})"
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
        assignments = assign_pipeline_to_agents(js, agent_vals, pipeline)
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
    nats_client: NATSClient = await nc(
        [str(cfg.NATS_SERVER_URL)],
        f"orchestrator-{id}",
    )
    js: JetStreamContext = nats_client.jetstream()

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
