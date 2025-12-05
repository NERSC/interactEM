import anyio
from nats.js import JetStreamContext
from pydantic import ValidationError

from interactem.core.events.deployments import (
    AgentDeploymentRunEvent,
    AgentDeploymentStopEvent,
    AgentOperatorRestartEvent,
    DeploymentAssignmentsEvent,
    DeploymentRunEvent,
    DeploymentStopEvent,
    OperatorRestartEvent,
)
from interactem.core.logger import get_logger
from interactem.core.models.canonical import CanonicalPipeline
from interactem.core.nats.publish import (
    publish_agent_deployment_event,
    publish_deployment_assignment,
)
from interactem.core.pipeline import Pipeline

from .assign import PipelineAssigner
from .exceptions import (
    InvalidPipelineError,
    NoAgentAssignmentsError,
    OperatorNotFoundError,
)
from .state import OrchestratorState

logger = get_logger()


async def handle_run_deployment(
    event: DeploymentRunEvent,
    js: JetStreamContext,
    state: OrchestratorState,
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
    agents = state.agents
    agent_vals = list(agents.values())

    assigner = PipelineAssigner(agent_vals, pipeline)
    assignments = assigner.assign()

    # assign deployment (this will also create the deployment state machine)
    deployment_sm = await state.get_deployment_sm(event.deployment_id)
    await deployment_sm.assign()

    async with anyio.create_task_group() as tg:
        for assignment in assignments:
            ev = AgentDeploymentRunEvent(
                agent_id=assignment.agent_id,
                assignment=assignment,
                deployment_id=event.deployment_id,
            )
            tg.start_soon(publish_agent_deployment_event, js, ev)

    logger.info(f"Published {len(assignments)} assignments for pipeline {pipeline.id}.")

    assignments_event = DeploymentAssignmentsEvent(
        deployment_id=event.deployment_id, assignments=assignments
    )
    async with anyio.create_task_group() as tg:
        # After we send the assignment to the agent,
        # we publish the assignment events
        # so that the fastapi knows, and we can look at these later
        tg.start_soon(publish_deployment_assignment, js, assignments_event)


async def handle_stop_deployment_event(
    event: DeploymentStopEvent,
    js: JetStreamContext,
    state: OrchestratorState,
):
    deployment_id = event.deployment_id
    agents = state.agents

    stop_events = [
        AgentDeploymentStopEvent(
            agent_id=agent_id,
            deployment_id=deployment_id,
        )
        for agent_id in list(agents.keys())
    ]

    sm = await state.get_deployment_sm(deployment_id)
    async with anyio.create_task_group() as tg:
        tg.start_soon(sm.cancel)
        for e in stop_events:
            tg.start_soon(publish_agent_deployment_event, js, e)

    logger.info(f"Pipeline stop event for {deployment_id} processed.")


async def handle_restart_operator_event(
    event: OperatorRestartEvent, js: JetStreamContext, state: OrchestratorState
):
    """Handle operator restart requests by forwarding to relevant agents."""

    deployment_id = event.deployment_id
    canonical_operator_id = event.canonical_operator_id

    matching_operators = [
        op
        for op in state.operators.values()
        if op.canonical_id == canonical_operator_id
        and op.runtime_pipeline_id == deployment_id
    ]

    if not matching_operators:
        raise OperatorNotFoundError

    agent_ids = set()
    for agent_id, agent_val in state.agents.items():
        if agent_val.current_deployment_id != deployment_id:
            continue

        assignments = agent_val.operator_assignments or []
        if any(op.id in assignments for op in matching_operators):
            agent_ids.add(agent_id)

    if not agent_ids:
        raise NoAgentAssignmentsError

    async with anyio.create_task_group() as tg:
        for agent_id in agent_ids:
            restart_event = AgentOperatorRestartEvent(
                agent_id=agent_id,
                deployment_id=deployment_id,
                canonical_operator_id=canonical_operator_id,
            )
            tg.start_soon(publish_agent_deployment_event, js, restart_event)

    logger.info(
        "Restart events published for canonical operator %s on deployment %s to %d agents",
        canonical_operator_id,
        deployment_id,
        len(agent_ids),
    )
