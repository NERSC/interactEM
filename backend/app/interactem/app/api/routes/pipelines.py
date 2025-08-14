import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError
from sqlmodel import col, func, select

from interactem.app.api.deps import CurrentUser, SessionDep
from interactem.app.api.routes.utils import check_present_and_authorized
from interactem.app.models import (
    Message,
    Pipeline,
    PipelineCreate,
    PipelineDeployment,
    PipelineDeploymentPublic,
    PipelineDeploymentsPublic,
    PipelinePublic,
    PipelineRevision,
    PipelineRevisionCreate,
    PipelineRevisionPublic,
    PipelineRevisionUpdate,
    PipelinesPublic,
    PipelineUpdate,
)
from interactem.core.logger import get_logger
from interactem.core.models.canonical import (
    CanonicalPipeline,
    CanonicalPipelineRevisionID,
)

logger = get_logger()
router = APIRouter()


@router.get("/", response_model=PipelinesPublic)
def read_pipelines(
    session: SessionDep,
    current_user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> PipelinesPublic:
    """
    Retrieve pipelines, ordered by last updated. Includes pipeline name.
    """
    common_query = select(Pipeline).order_by(col(Pipeline.updated_at).desc())
    count_query = select(func.count()).select_from(Pipeline)

    if not current_user.is_superuser:
        common_query = common_query.where(Pipeline.owner_id == current_user.id)
        count_query = count_query.where(Pipeline.owner_id == current_user.id)

    count = session.exec(count_query).one()
    pipelines_db = session.exec(common_query.offset(offset).limit(limit)).all()

    # Validate data before returning - ensures name is included
    pipelines_public = [PipelinePublic.model_validate(p) for p in pipelines_db]

    return PipelinesPublic(data=pipelines_public, count=count)


@router.get("/{id}", response_model=PipelinePublic)
def read_pipeline(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get pipeline by ID.
    """
    pipeline = session.get(Pipeline, id)
    pipeline = check_present_and_authorized(pipeline, current_user, id)
    return PipelinePublic.model_validate(pipeline)


@router.patch("/{id}", response_model=PipelinePublic)
def update_pipeline(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    update: PipelineUpdate,
) -> Any:
    """
    Update a pipeline's name.
    """
    pipeline = session.get(Pipeline, id)
    pipeline = check_present_and_authorized(pipeline, current_user, id)

    if not update.name:
        raise HTTPException(status_code=400, detail="Pipeline name is required")

    pipeline.name = update.name
    pipeline.updated_at = datetime.now(timezone.utc)
    session.add(pipeline)
    session.commit()
    session.refresh(pipeline)
    return PipelinePublic.model_validate(pipeline)


@router.get("/{id}/revisions", response_model=list[PipelineRevisionPublic])
def list_pipeline_revisions(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    List revisions for a pipeline (paginated).
    """
    # Check pipeline existence and permissions first
    pipeline = session.get(Pipeline, id)
    check_present_and_authorized(pipeline, current_user, id)

    statement = (
        select(PipelineRevision)
        .where(col(PipelineRevision.pipeline_id) == id)
        .order_by(col(PipelineRevision.revision_id).desc())
        .offset(offset)
        .limit(limit)
    )

    revisions_db = session.exec(statement).all()

    revisions_public = [PipelineRevisionPublic.model_validate(r) for r in revisions_db]
    return revisions_public


@router.post("/{id}/revisions", response_model=PipelineRevisionPublic)
def add_pipeline_revision(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    revision_in: PipelineRevisionCreate,
):
    """
    Add a new revision to a pipeline.
    """
    if not revision_in.data:
        raise HTTPException(status_code=400, detail="Revision data is required")
    # Lock this pipeline to avoid race condition with revision ID
    pipeline = session.get(Pipeline, id, with_for_update=True)
    pipeline = check_present_and_authorized(pipeline, current_user, id)

    # Get latest revision_id
    statement = (
        select(PipelineRevision.revision_id)
        .where(col(PipelineRevision.pipeline_id) == id)
        .order_by(col(PipelineRevision.revision_id).desc())
        .limit(1)
    )
    last_revision = session.exec(statement).first()
    next_revision_id = (last_revision or 0) + 1

    # Create the new revision
    revision = PipelineRevision(
        pipeline_id=id,
        revision_id=next_revision_id,
        data=revision_in.data,
    )
    session.add(revision)

    try:
        CanonicalPipeline(
            id=revision.pipeline_id, revision_id=revision.revision_id, **revision.data
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=f"Invalid pipeline data: {str(e)}")

    # Update the parent pipeline
    pipeline.data = revision_in.data
    pipeline.updated_at = datetime.now(timezone.utc)
    pipeline.current_revision_id = next_revision_id
    session.add(pipeline)

    try:
        session.commit()
        session.refresh(revision)
        session.refresh(pipeline)
    except Exception as e:
        session.rollback()
        logger.error(f"Error adding revision: {e}")
        raise HTTPException(status_code=500, detail="Failed to save pipeline revision.")

    # Validate before returning
    return PipelineRevisionPublic.model_validate(revision)


@router.get("/{id}/revisions/{revision_id}", response_model=PipelineRevisionPublic)
def read_pipeline_revision(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    revision_id: CanonicalPipelineRevisionID,
) -> Any:
    """
    Get specific revision data for a pipeline.
    """
    # Use composite primary key lookup
    revision = session.get(PipelineRevision, (id, revision_id))

    if not revision:
        raise HTTPException(status_code=404, detail="Pipeline revision not found")

    # Check ownership via the related pipeline
    pipeline = revision.pipeline
    check_present_and_authorized(pipeline, current_user, id)

    return PipelineRevisionPublic.model_validate(revision)


@router.patch("/{id}/revisions/{revision_id}", response_model=PipelineRevisionPublic)
def update_pipeline_revision(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    revision_id: CanonicalPipelineRevisionID,
    update: PipelineRevisionUpdate,
) -> PipelineRevisionPublic:
    """
    Update a specific pipeline revision.
    """
    revision = session.get(PipelineRevision, (id, revision_id))
    if not revision:
        raise HTTPException(status_code=404, detail="Pipeline revision not found")

    # Check ownership via the related pipeline
    pipeline = revision.pipeline
    check_present_and_authorized(pipeline, current_user, id)

    revision.tag = update.tag
    session.add(revision)
    session.commit()
    session.refresh(revision)

    return PipelineRevisionPublic.model_validate(revision)


@router.post("/", response_model=PipelinePublic)
def create_pipeline(
    *, session: SessionDep, current_user: CurrentUser, pipeline_in: PipelineCreate
) -> PipelinePublic:
    """
    Create new pipeline.
    """
    pipeline = Pipeline.model_validate(
        pipeline_in, update={"owner_id": current_user.id}
    )
    session.add(pipeline)
    session.commit()
    session.refresh(pipeline)
    pipeline = PipelinePublic.model_validate(pipeline)
    return pipeline


@router.delete("/{id}")
def delete_pipeline(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete an pipeline.
    """
    pipeline = session.get(Pipeline, id)
    check_present_and_authorized(pipeline, current_user, id)
    session.delete(pipeline)
    session.commit()
    return Message(message="Pipeline deleted successfully")


@router.get("/{id}/deployments", response_model=PipelineDeploymentsPublic)
def list_pipeline_deployments(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PipelineDeploymentsPublic:
    """
    List deployments for a pipeline.
    """
    pipeline = session.get(Pipeline, id)
    pipeline = check_present_and_authorized(pipeline, current_user, id)

    all_deployments: list[PipelineDeployment] = []
    for revision in pipeline.revisions:
        all_deployments.extend(revision.deployments)

    all_deployments.sort(key=lambda deployment: deployment.created_at, reverse=True)

    total_count = len(all_deployments)
    paginated_deployments = all_deployments[offset : offset + limit]

    deployments_public = [
        PipelineDeploymentPublic.model_validate(r) for r in paginated_deployments
    ]
    return PipelineDeploymentsPublic(data=deployments_public, count=total_count)


@router.get(
    "/{id}/revisions/{revision_id}/deployments",
    response_model=PipelineDeploymentsPublic,
)
def list_pipeline_revision_deployments(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    revision_id: CanonicalPipelineRevisionID,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> PipelineDeploymentsPublic:
    """
    List all deployments for a specific pipeline revision.
    """
    pipeline = session.get(Pipeline, id)
    pipeline = check_present_and_authorized(pipeline, current_user, id)

    revision = session.get(PipelineRevision, (id, revision_id))
    if not revision:
        raise HTTPException(status_code=404, detail="Pipeline revision not found")

    all_deployments = revision.deployments
    all_deployments.sort(key=lambda deployment: deployment.created_at, reverse=True)

    total_count = len(all_deployments)
    paginated_deployments = all_deployments[offset : offset + limit]

    deployments_public = [
        PipelineDeploymentPublic.model_validate(r) for r in paginated_deployments
    ]
    return PipelineDeploymentsPublic(data=deployments_public, count=total_count)
