import anyio
from nats.js import JetStreamContext
from pydantic import ValidationError

from interactem.core.events.pipelines import (
    AgentPipelineRunEvent,
    AgentPipelineStopEvent,
    PipelineAssignmentsEvent,
    PipelineRunEvent,
    PipelineStopEvent,
)
from interactem.core.logger import get_logger
from interactem.core.models.canonical import CanonicalPipeline
from interactem.core.nats.publish import (
    publish_agent_deployment_event,
    publish_deployment_assignment,
)
from interactem.core.pipeline import Pipeline

from .assign import PipelineAssigner
from .exceptions import InvalidPipelineError
from .state import OrchestratorState

logger = get_logger()


async def handle_run_pipeline(
    event: PipelineRunEvent,
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
            ev = AgentPipelineRunEvent(
                agent_id=assignment.agent_id,
                assignment=assignment,
                deployment_id=event.deployment_id,
            )
            tg.start_soon(publish_agent_deployment_event, js, ev)

    logger.info(f"Published {len(assignments)} assignments for pipeline {pipeline.id}.")

    assignments_event = PipelineAssignmentsEvent(
        deployment_id=event.deployment_id, assignments=assignments
    )
    async with anyio.create_task_group() as tg:
        # After we send the assignment to the agent,
        # we publish the assignment events
        # so that the fastapi knows, and we can look at these later
        tg.start_soon(publish_deployment_assignment, js, assignments_event)


async def handle_stop_pipeline_event(
    event: PipelineStopEvent,
    js: JetStreamContext,
    state: OrchestratorState,
):
    deployment_id = event.deployment_id
    agents = state.agents

    stop_events = [
        AgentPipelineStopEvent(
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
