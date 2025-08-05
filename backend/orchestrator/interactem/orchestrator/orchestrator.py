import asyncio
import random
from uuid import UUID, uuid4

import networkx as nx
from nats.aio.client import Client as NATSClient
from nats.aio.msg import Msg as NATSMsg
from nats.js import JetStreamContext
from pydantic import BaseModel, ValidationError

from interactem.core.constants import (
    AGENTS,
    BUCKET_STATUS,
    BUCKET_STATUS_TTL,
    NATS_API_KEY_HEADER,
    PIPELINES,
    STREAM_DEPLOYMENTS,
    SUBJECT_PIPELINES_DEPLOYMENTS_UPDATE,
)
from interactem.core.events.pipelines import (
    PipelineDeploymentEvent,
    PipelineStopEvent,
    PipelineUpdateEvent,
)
from interactem.core.logger import get_logger
from interactem.core.models.base import IdType, PipelineDeploymentState
from interactem.core.models.canonical import CanonicalPipeline
from interactem.core.models.kvs import AgentVal, PipelineRunVal
from interactem.core.models.runtime import PipelineAssignment, RuntimeOperator
from interactem.core.nats import (
    consume_messages,
    create_bucket_if_doesnt_exist,
    create_or_update_stream,
    get_keys,
    get_status_bucket,
    get_val,
    nc,
    publish_error,
    publish_notification,
)
from interactem.core.nats.config import DEPLOYMENTS_STREAM_CONFIG
from interactem.core.nats.consumers import (
    create_orchestrator_pipeline_new_consumer,
    create_orchestrator_pipeline_stop_consumer,
)
from interactem.core.nats.publish import publish_assignment
from interactem.core.pipeline import Pipeline

from .config import cfg

logger = get_logger()

pipelines: dict[IdType, PipelineDeploymentEvent] = {}

task_refs: set[asyncio.Task] = set()


class CyclicDependenciesError(Exception):
    pass


class NoAgentsError(Exception):
    pass


class UnassignableOperatorsError(Exception):
    pass


class NetworkPreferenceError(Exception):
    pass


async def delete_pipeline_kv(js: JetStreamContext, pipeline_id: IdType):
    pipeline_bucket = await get_status_bucket(js)
    key = f"{PIPELINES}.{str(pipeline_id)}"  # TODO: use PipelineRunVal.key() instead
    await pipeline_bucket.delete(key)
    await pipeline_bucket.purge(key)


async def update_pipeline_kv(
    js: JetStreamContext, pipeline: PipelineRunVal | PipelineDeploymentEvent
):
    if isinstance(pipeline, PipelineDeploymentEvent):
        pipeline = PipelineRunVal(
            id=pipeline.deployment_id,
            canonical_id=pipeline.canonical_id,
            canonical_revision_id=pipeline.revision_id,
        )
    pipeline_bucket = await get_status_bucket(js)
    await pipeline_bucket.put(pipeline.key(), pipeline.model_dump_json().encode())


async def continuous_update_kv(js: JetStreamContext, interval: int = 10):
    while True:
        for pipeline in pipelines.values():
            await update_pipeline_kv(js, pipeline)
        logger.debug(f"Updated {len(pipelines)} pipelines in KV store.")
        await asyncio.sleep(interval)

async def update_pipeline_status(
    js: JetStreamContext,
    event: PipelineDeploymentEvent,
    state: PipelineDeploymentState,
):
    update_event = PipelineUpdateEvent(deployment_id=event.deployment_id, state=state)
    await js.publish(
        SUBJECT_PIPELINES_DEPLOYMENTS_UPDATE,
        stream=STREAM_DEPLOYMENTS,
        payload=update_event.model_dump_json().encode(),
        headers={NATS_API_KEY_HEADER: cfg.ORCHESTRATOR_API_KEY},
    )


async def clean_up_old_pipelines(
    js: JetStreamContext, valid_pipeline: CanonicalPipeline
):
    bucket = await get_status_bucket(js)
    current_pipeline_keys = await get_keys(bucket, filters=[f"{PIPELINES}"])
    delete_tasks = []
    for key in current_pipeline_keys:
        key = key.strip(f"{PIPELINES}.")
        if key != str(valid_pipeline.id):
            try:
                uid = UUID(key)
                delete_tasks.append(delete_pipeline_kv(js, uid))
                logger.debug(f"Scheduled deletion for old pipeline key: {key}")
            except ValueError:
                logger.warning(f"Skipping deletion of non-UUID pipeline key: {key}")
    if delete_tasks:
        await asyncio.gather(*delete_tasks)
        logger.info(f"Deleted {len(delete_tasks)} old pipeline entries from KV store.")

    pipelines.clear()


class AssignmentState(BaseModel):
    assignments: dict[IdType, list[RuntimeOperator]]
    operator_networks: dict[IdType, set[str]]


class PipelineAssigner:
    """
    Assigns pipeline operators to agents based on tag matching, network preferences, and load balancing.

    - Processes operators in topological order (dependencies first).
    - For each operator, finds agents matching required tags.
    - Prefers agents on the same network as upstream assignments.
    - Balances assignments by agent load.
    - Raises errors if operators cannot be assigned due to cycles, missing agents, or network constraints.
    """

    def __init__(self, agent_infos: list[AgentVal], pipeline: Pipeline):
        self.agent_infos = agent_infos

        if not agent_infos:
            raise NoAgentsError("No agents available for assignment.")

        self.pipeline = pipeline
        self.operator_graph = pipeline.get_operator_graph()
        self.sorted_operator_ids: list[IdType] = []

        # Ensure all operators are in the graph for sorting
        all_op_ids = set(pipeline.operators.keys())
        graph_nodes = set(self.operator_graph.nodes())
        if all_op_ids != graph_nodes:
            # This will happen if there are disconnected nodes (e.g. service nodes)
            missing_nodes = all_op_ids - graph_nodes
            self.operator_graph.add_nodes_from(missing_nodes)

        # Topological sort - this will fail if there are cycles
        try:
            self.sorted_operator_ids = list(nx.topological_sort(self.operator_graph))
            logger.debug(f"Operator assignment order: {self.sorted_operator_ids}")
        except nx.NetworkXUnfeasible as e:
            logger.exception(
                f"Pipeline {pipeline.id} contains cycles and cannot be assigned."
            )
            raise CyclicDependenciesError(
                f"Pipeline {pipeline.id} contains cycles."
            ) from e

    def assign(self) -> list[PipelineAssignment]:
        state = AssignmentState(
            assignments={agent.uri.id: [] for agent in self.agent_infos},
            operator_networks={},
        )
        unassignable_operators: list[tuple[IdType, str]] = []  # (Operator ID, reason)

        for op_id in self.sorted_operator_ids:
            operator = self.pipeline.operators.get(op_id)
            if not operator:
                unassignable_operators.append((op_id, "Operator not found"))
                continue

            candidates = self._find_agents_matching_tags(operator)
            if not candidates:
                unassignable_operators.append((op_id, "No matching agents"))
                continue

            allowed_networks = self._determine_allowed_networks(op_id, state)
            eligible_agents = self._filter_agents_by_networks(
                candidates, allowed_networks
            )
            best_agent = self._select_best_agent(eligible_agents, state)

            if not best_agent:
                unassignable_operators.append((op_id, "No eligible agent"))
                continue

            self._record_assignment(
                state, op_id, operator, best_agent, allowed_networks
            )

        if unassignable_operators:
            error_details = "; ".join(
                [f"Op {op_id}: {reason}" for op_id, reason in unassignable_operators]
            )
            network_failures = any(
                "network" in reason for _, reason in unassignable_operators
            )
            if network_failures:
                raise NetworkPreferenceError(
                    f"Could not assign one or more operators in pipeline {self.pipeline.id}. Details: {error_details}"
                )
            else:
                raise UnassignableOperatorsError(
                    f"Could not assign one or more operators in pipeline {self.pipeline.id}. Details: {error_details}"
                )

        final_assignments = []
        runtime_pipeline = self.pipeline.to_runtime()

        for agent in self.agent_infos:
            agent_id = agent.uri.id
            # we want to assign blank operators to agents that are not assigned any
            # so that they will shut down their operators (one pipeline at a time)
            assigned_runtime_operators = state.assignments.get(agent_id, [])
            # The assigned operators are already runtime operators with runtime IDs
            assigned_runtime_ids = [op.id for op in assigned_runtime_operators]
            assignment = PipelineAssignment(
                agent_id=agent_id,
                operators_assigned=assigned_runtime_ids,
                pipeline=runtime_pipeline,
            )
            final_assignments.append(assignment)

        self.log_assignments(final_assignments)
        return final_assignments

    def _find_agents_matching_tags(self, operator: RuntimeOperator) -> list[AgentVal]:
        op_tag_values = {tag.value for tag in operator.tags}
        if not op_tag_values:
            return self.agent_infos
        return [
            agent
            for agent in self.agent_infos
            if op_tag_values.issubset(set(agent.tags))
        ]

    def _determine_allowed_networks(
        self, op_id: IdType, state: AssignmentState
    ) -> set[str] | None:
        predecessor_networks = self._get_predecessor_networks(op_id, state)
        if predecessor_networks:
            return predecessor_networks
        return None  # No restriction for first operator

    def _get_predecessor_networks(
        self, operator_id: IdType, state: AssignmentState
    ) -> set[str]:
        upstream_op_ids = list(self.operator_graph.predecessors(operator_id))
        assigned_upstream_networks = set()
        for up_op_id in upstream_op_ids:
            if up_op_id in state.operator_networks:
                assigned_upstream_networks.update(state.operator_networks[up_op_id])
        return assigned_upstream_networks

    def _filter_agents_by_networks(
        self, tag_matching_agents: list[AgentVal], allowed_networks: set[str] | None
    ) -> list[AgentVal]:
        if allowed_networks is not None:
            eligible_agents = [
                agent
                for agent in tag_matching_agents
                if allowed_networks.intersection(agent.networks)
            ]
            if eligible_agents:
                return eligible_agents
        return tag_matching_agents

    def _select_best_agent(
        self, candidate_agents: list[AgentVal], state: AssignmentState
    ) -> AgentVal | None:
        if not candidate_agents:
            return None
        min_load = min(
            len(state.assignments.get(agent.uri.id, [])) for agent in candidate_agents
        )
        least_loaded_agents = [
            agent
            for agent in candidate_agents
            if len(state.assignments.get(agent.uri.id, [])) == min_load
        ]
        return random.choice(least_loaded_agents)

    def _record_assignment(
        self,
        state: AssignmentState,
        op_id: IdType,
        operator: RuntimeOperator,
        agent: AgentVal,
        allowed_networks: set[str] | None,
    ):
        agent_id = agent.uri.id
        agent_networks = agent.networks
        if allowed_networks is not None:
            assigned_networks = agent_networks.intersection(allowed_networks)
            if not assigned_networks:
                # Fallback: assign all agent networks (should not happen if filtered correctly)
                assigned_networks = agent_networks
        else:
            # First operator: assign all agent networks
            assigned_networks = agent_networks
        state.assignments[agent_id].append(operator)
        state.operator_networks[op_id] = assigned_networks
        logger.debug(
            f"Assigned operator {op_id} to agent {agent_id} on networks {sorted(assigned_networks)}"
        )

    def log_assignments(self, pipeline_assignments: list[PipelineAssignment]) -> None:
        """Generate and log human-readable assignment information"""
        log_context = f"Pipeline {self.pipeline.id}"

        if not self.pipeline.operators:
            logger.info(
                f"Assignment complete for {log_context}: Pipeline has no operators."
            )
            return

        log_lines = [
            "\n" + "-" * 20 + f" Assignment Summary: {log_context} " + "-" * 20
        ]

        if not pipeline_assignments:
            # Should only happen if pipeline was empty
            log_lines.append("No operators assigned.")
            logger.info("\n".join(log_lines))
            return

        for assignment in pipeline_assignments:
            agent_id = assignment.agent_id
            agent = next((a for a in self.agent_infos if a.uri.id == agent_id), None)
            if not agent:  # Should not happen
                log_lines.append(f"Agent {agent_id} (Info not found):")
                log_lines.append(f"  Operators: {assignment.operators_assigned}")
                continue

            log_lines.append(
                f"Agent {agent_id} (Tags: {agent.tags}, Networks: {agent.networks}):"
            )
            if not assignment.operators_assigned:
                log_lines.append("  <No operators assigned>")
                continue

            for op_id in assignment.operators_assigned:
                op = self.pipeline.operators.get(op_id)
                op_tags_str = (
                    f"(Tags: {[t.value for t in op.tags]})"
                    if op and op.tags
                    else "(No tags)"
                )
                op_image_str = f"{op.image} " if op else ""
                canonical_id_str = (
                    f" (canonical: {op.canonical_id})"
                    if op and hasattr(op, "canonical_id")
                    else ""
                )
                log_lines.append(
                    f"  - Operator {op_image_str}({op_id}){canonical_id_str} {op_tags_str}"
                )

        log_lines.append("-" * (40 + len(f" Assignment Summary: {log_context} ")))
        logger.info("\n".join(log_lines))


async def handle_run_pipeline(msg: NATSMsg, js: JetStreamContext):
    logger.info("Received pipeline run event...")

    try:
        event = PipelineDeploymentEvent.model_validate_json(msg.data)
    except ValidationError as e:
        logger.error(f"Invalid pipeline run event message: {e}")
        await msg.term()
        return

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

    await asyncio.gather(
        *[publish_assignment(js, assignment) for assignment in assignments]
    )
    logger.info(f"Published {len(assignments)} assignments for pipeline {pipeline.id}.")

    await clean_up_old_pipelines(js, valid_pipeline)

    await update_pipeline_kv(js, event)
    pipelines[valid_pipeline.id] = event
    logger.info(f"Updated KV store with pipeline {valid_pipeline.id}.")

    logger.info(f"Pipeline run event for {valid_pipeline.id} processed.")


async def handle_stop_pipeline(msg: NATSMsg, js: JetStreamContext):
    logger.info("Received pipeline stop event...")
    await msg.ack()

    try:
        event = PipelineStopEvent.model_validate_json(msg.data)
    except ValidationError as e:
        logger.error(f"Invalid pipeline stop event message: {e}")
        return

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

    agent_ids = [UUID(agent_key.strip(f"{AGENTS}.")) for agent_key in agent_keys]

    # Create a runtime pipeline w/o operators for killing the pipelin

    # TODO: for now, we use a blank pipeline to stop things
    # we should probably have a more explicit "stop" pipeline message
    canonical_pipeline = CanonicalPipeline(
        id=event.deployment_id, revision_id=0, operators=[], edges=[]
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


async def main():
    instance_id: UUID = uuid4()
    nats_client: NATSClient = await nc(
        [str(cfg.NATS_SERVER_URL)],
        f"orchestrator-{instance_id}",
    )
    js: JetStreamContext = nats_client.jetstream()

    logger.info(f"Orchestrator instance {instance_id} starting...")

    try:
        startup_tasks = [
            create_bucket_if_doesnt_exist(js, BUCKET_STATUS, BUCKET_STATUS_TTL),
            create_or_update_stream(DEPLOYMENTS_STREAM_CONFIG, js),
        ]
        await asyncio.gather(*startup_tasks)
        logger.info("NATS buckets and streams initialized/verified.")

        pipeline_run_psub = await create_orchestrator_pipeline_new_consumer(
            js, instance_id
        )
        logger.info("Pipeline run event consumer created.")

        pipeline_stop_psub = await create_orchestrator_pipeline_stop_consumer(
            js, instance_id
        )
        logger.info("Pipeline stop event consumer created.")

        update_task = asyncio.create_task(continuous_update_kv(js))
        task_refs.add(update_task)

        run_consumer_task = asyncio.create_task(
            consume_messages(pipeline_run_psub, handle_run_pipeline, js)
        )
        task_refs.add(run_consumer_task)

        stop_consumer_task = asyncio.create_task(
            consume_messages(pipeline_stop_psub, handle_stop_pipeline, js)
        )
        task_refs.add(stop_consumer_task)

        logger.info(
            f"Orchestrator instance {instance_id} running. Waiting for events..."
        )
        await asyncio.gather(run_consumer_task, stop_consumer_task, update_task)

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
