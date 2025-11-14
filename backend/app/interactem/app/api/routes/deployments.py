# interactem.app.api.routes.deployments

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, desc, select

from interactem.app.api.deps import CurrentUser, SessionDep
from interactem.app.core.util import (
    check_present_and_authorized,
)
from interactem.app.events.producer import (
    publish_pipeline_deployment_event,
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
from interactem.core.events.pipelines import (
    PipelineRunEvent,
    PipelineStopEvent,
)
from interactem.core.logger import get_logger

logger = get_logger()
router = APIRouter()


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
    Create a new pipeline deployment and publish initialization event.
    State transitions are managed by the orchestrator.
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

    # Publish initialization event for orchestrator to handle
    event = PipelineRunEvent(
        canonical_id=deployment.pipeline_id,
        data=deployment.revision.data,
        revision_id=deployment.revision_id,
        deployment_id=deployment.id,
    )
    await publish_pipeline_deployment_event(event)

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
    Update a pipeline deployment state and publish events for the orchestrator.
    """
    deployment = session.get(PipelineDeployment, id)
    deployment = check_deployment_authorized(deployment, current_user, id)

    new_state = update.state

    # Update the state
    deployment.state = new_state
    session.add(deployment)
    session.commit()
    session.refresh(deployment)

    # Publish events for orchestrator to handle
    if new_state == PipelineDeploymentState.CANCELLED:
        event = PipelineStopEvent(deployment_id=deployment.id)
        await publish_pipeline_deployment_event(event)
        logger.info(f"Published stop event for deployment {deployment.id}")

    return PipelineDeploymentPublic.model_validate(deployment)
