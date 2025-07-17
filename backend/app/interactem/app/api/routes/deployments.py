# interactem.app.api.routes.deployments

import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, desc, select

from interactem.app.api.deps import CurrentUser, SessionDep
from interactem.app.api.routes.utils import check_present_and_authorized
from interactem.app.events.producer import (
    publish_pipeline_run_event,
    publish_pipeline_stop_event,
)
from interactem.app.models import (
    Pipeline,
    PipelineDeployment,
    PipelineDeploymentCreate,
    PipelineDeploymentPublic,
    PipelineDeploymentsPublic,
    PipelineDeploymentState,
    PipelineDeploymentUpdate,
    PipelineRevision,
)
from interactem.core.events.pipelines import PipelineRunEvent, PipelineStopEvent
from interactem.core.logger import get_logger

logger = get_logger()
router = APIRouter()


class PipelineDeploymentStateMachine:
    class Error(Exception):
        pass

    """Handles pipeline deployment state transitions and NATS event publishing."""

    def __init__(self):
        self._valid_transitions: dict[
            PipelineDeploymentState, list[PipelineDeploymentState]
        ] = {
            PipelineDeploymentState.PENDING: [
                PipelineDeploymentState.FAILED_TO_START,
                PipelineDeploymentState.RUNNING,
                PipelineDeploymentState.CANCELLED,
            ],
            PipelineDeploymentState.FAILED_TO_START: [],
            PipelineDeploymentState.RUNNING: [
                PipelineDeploymentState.CANCELLED,
            ],
            PipelineDeploymentState.CANCELLED: [],
        }

        self._transition_handlers: dict[
            tuple[PipelineDeploymentState, PipelineDeploymentState], Callable
        ] = {
            (
                PipelineDeploymentState.PENDING,
                PipelineDeploymentState.RUNNING,
            ): self._handle_started,
            (
                PipelineDeploymentState.PENDING,
                PipelineDeploymentState.FAILED_TO_START,
            ): self._handle_failed_to_start,
            (
                PipelineDeploymentState.PENDING,
                PipelineDeploymentState.CANCELLED,
            ): self._handle_cancellation,
            (
                PipelineDeploymentState.RUNNING,
                PipelineDeploymentState.CANCELLED,
            ): self._handle_cancellation,
        }

    async def start(self, deployment: PipelineDeployment) -> None:
        event = PipelineRunEvent(
            id=deployment.pipeline_id,
            data=deployment.revision.data,
            revision_id=deployment.revision_id,
            deployment_id=deployment.id,
        )
        await publish_pipeline_run_event(event)
        logger.info(f"Sent deployment event for deployment {deployment.id}")

    def is_valid_transition(
        self, from_state: PipelineDeploymentState, to_state: PipelineDeploymentState
    ) -> bool:
        return to_state in self._valid_transitions.get(from_state, [])

    async def handle_transition(
        self,
        deployment: PipelineDeployment,
        from_state: PipelineDeploymentState,
        to_state: PipelineDeploymentState,
    ) -> None:
        transition_key = (from_state, to_state)
        handler = self._transition_handlers.get(transition_key)

        if handler:
            await handler(deployment)
        else:
            logger.warning(f"No handler for transition {from_state} -> {to_state}")

    async def _handle_cancellation(self, deployment: PipelineDeployment) -> None:
        event = PipelineStopEvent(
            id=deployment.pipeline_id,
            revision_id=deployment.revision_id,
            deployment_id=deployment.id,
        )
        await publish_pipeline_stop_event(event)
        logger.info(f"Sent stop event for cancelled deployment {deployment.id}")

    async def _handle_started(self, deployment: PipelineDeployment) -> None:
        pass

    async def _handle_failed_to_start(self, deployment: PipelineDeployment) -> None:
        logger.info(f"Deployment {deployment.id} failed to start")


state_machine = PipelineDeploymentStateMachine()


def check_deployment_authorized(
    deployment: PipelineDeployment | None,
    current_user: CurrentUser,
    deployment_id: uuid.UUID,
) -> PipelineDeployment:
    if not deployment:
        raise HTTPException(status_code=404, detail="Pipeline deployment not found")
    pipeline = deployment.revision.pipeline
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=404, detail="Pipeline deployment not found")
    return deployment


@router.get("/", response_model=PipelineDeploymentsPublic)
def list_pipeline_deployments(
    session: SessionDep,
    current_user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    states: list[PipelineDeploymentState] | None = Query(default=None),
    pipeline_id: uuid.UUID | None = Query(default=None),
) -> Any:
    """
    Get all pipeline deployments accessible to the current user with pagination.
    Optionally filter by state.
    """
    if current_user.is_superuser:
        # Superusers can see all deployments
        statement = (
            select(PipelineDeployment)
            .offset(offset)
            .limit(limit)
            .order_by(desc(PipelineDeployment.created_at))
        )
    else:
        statement = (
            select(PipelineDeployment)
            .join(PipelineRevision)
            .join(Pipeline)
            .where(Pipeline.owner_id == current_user.id)
            .offset(offset)
            .limit(limit)
            .order_by(desc(PipelineDeployment.created_at))
        )

    if states is not None:
        statement = statement.where(col(PipelineDeployment.state).in_(states))

    if pipeline_id is not None:
        statement = statement.where(PipelineDeployment.pipeline_id == pipeline_id)

    results = session.exec(statement).all()
    deployment_publics = [
        PipelineDeploymentPublic.model_validate(deployment) for deployment in results
    ]

    return PipelineDeploymentsPublic(
        data=deployment_publics, count=len(deployment_publics)
    )


@router.post("/", response_model=PipelineDeploymentPublic)
async def create_pipeline_deployment(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    deployment_in: PipelineDeploymentCreate,
) -> PipelineDeploymentPublic:
    """
    Create a new pipeline deployment and trigger execution.
    """

    pipeline = session.get(Pipeline, deployment_in.pipeline_id)
    check_present_and_authorized(pipeline, current_user, deployment_in.pipeline_id)

    revision = session.get(
        PipelineRevision, (deployment_in.pipeline_id, deployment_in.revision_id)
    )
    if not revision:
        raise HTTPException(status_code=404, detail="Pipeline revision not found")

    deployment = PipelineDeployment(
        pipeline_id=deployment_in.pipeline_id,
        revision_id=deployment_in.revision_id,
        state=PipelineDeploymentState.PENDING,
    )
    session.add(deployment)
    session.commit()
    session.refresh(deployment)

    try:
        await state_machine.start(deployment)
    except HTTPException:
        deployment.state = PipelineDeploymentState.FAILED_TO_START
        session.add(deployment)
        session.commit()
        session.refresh(deployment)
        await state_machine.handle_transition(
            deployment,
            PipelineDeploymentState.PENDING,
            PipelineDeploymentState.FAILED_TO_START,
        )
        raise

    logger.info(
        f"Created pipeline deployment {deployment.id} for pipeline {deployment_in.pipeline_id} revision {deployment_in.revision_id} in PENDING state"
    )

    return PipelineDeploymentPublic.model_validate(deployment)


@router.get("/{id}", response_model=PipelineDeploymentPublic)
def read_pipeline_deployment(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
) -> Any:
    """
    Get pipeline deployment by ID.
    """
    deployment = session.get(PipelineDeployment, id)
    deployment = check_deployment_authorized(deployment, current_user, id)
    return PipelineDeploymentPublic.model_validate(deployment)


@router.patch("/{id}", response_model=PipelineDeploymentPublic)
async def update_pipeline_deployment(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    update: PipelineDeploymentUpdate,
) -> PipelineDeploymentPublic:
    """
    Update a pipeline deployment state with proper transition logic and event publishing.
    """
    deployment = session.get(PipelineDeployment, id)
    deployment = check_deployment_authorized(deployment, current_user, id)

    # Store the previous state for transition logic
    previous_state = deployment.state
    new_state = update.state

    # Check if this is a no-op
    if previous_state == new_state:
        return PipelineDeploymentPublic.model_validate(deployment)

    # Validate state transition using our state machine
    if not state_machine.is_valid_transition(previous_state, new_state):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state transition from {previous_state} to {new_state}",
        )

    # Update the state
    deployment.state = new_state
    session.add(deployment)
    session.commit()
    session.refresh(deployment)

    # Handle transition events using our state machine
    try:
        await state_machine.handle_transition(deployment, previous_state, new_state)
    except PipelineDeploymentStateMachine.Error as e:
        logger.error(f"State machine error: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to handle state transition: {e}"
        )

    return PipelineDeploymentPublic.model_validate(deployment)
