import random

import networkx as nx

from interactem.core.logger import get_logger
from interactem.core.models.base import IdType
from interactem.core.models.kvs import AgentVal
from interactem.core.models.runtime import PipelineAssignment, RuntimeOperator
from interactem.core.pipeline import Pipeline

from .exceptions import (
    AssignmentState,
    CyclicDependenciesError,
    NetworkPreferenceError,
    NoAgentsError,
    UnassignableOperatorsError,
)

logger = get_logger()


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
