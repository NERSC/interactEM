import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, func, select

from interactem.app.api.deps import CurrentUser, SessionDep
from interactem.app.events.producer import publish_pipeline_run_event
from interactem.app.models import (
    Message,
    Pipeline,
    PipelineCreate,
    PipelinePublic,
    PipelineRevision,
    PipelinesPublic,
    PipelineUpdate,
)
from interactem.core.events.pipelines import PipelineRunEvent
from interactem.core.logger import get_logger

logger = get_logger()
router = APIRouter()


@router.get("/", response_model=PipelinesPublic)
def read_pipelines(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
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
    pipelines_db = session.exec(common_query.offset(skip).limit(limit)).all()

    # Validate data before returning - ensures name is included
    pipelines_public = [PipelinePublic.model_validate(p) for p in pipelines_db]

    return PipelinesPublic(data=pipelines_public, count=count)


@router.get("/{id}", response_model=PipelinePublic)
def read_pipeline(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get pipeline by ID.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
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
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")

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
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    List revisions for a pipeline (paginated).
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    statement = (
        select(PipelineRevision)
        .where(col(PipelineRevision.pipeline_id) == id)
        .order_by(col(PipelineRevision.revision_id).desc())
        .offset(skip)
        .limit(limit)
    )
    revisions = session.exec(statement).all()
    return revisions


@router.post("/{id}/revisions", response_model=PipelineRevision)
def add_pipeline_revision(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    revision_in: PipelineUpdate,
):
    """
    Add a new revision to a pipeline and update the pipeline's updated_at timestamp.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    # Get latest revision_id
    statement = (
        select(PipelineRevision.revision_id)
        .where(col(PipelineRevision.pipeline_id) == id)
        .order_by(col(PipelineRevision.revision_id).desc())
        .limit(1)
    )
    last_revision = session.exec(statement).first()
    next_revision_id = (last_revision or 0) + 1

    revision = PipelineRevision(
        pipeline_id=id,
        revision_id=next_revision_id,
        data=revision_in.data,
        tag=revision_in.tag,
    )
    session.add(revision)

    pipeline.data = revision_in.data
    pipeline.updated_at = datetime.now(timezone.utc)
    session.add(pipeline)

    session.commit()
    session.refresh(revision)
    session.refresh(pipeline)
    return revision


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
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(pipeline)
    session.commit()
    return Message(message="Pipeline deleted successfully")


@router.post("/{id}/run", response_model=PipelinePublic)
async def run_pipeline(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> PipelinePublic:
    """
    Run a pipeline.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    pipeline = PipelinePublic.model_validate(pipeline)

    try:
        await publish_pipeline_run_event(PipelineRunEvent(**pipeline.model_dump()))
        logger.info(f"Sent publish pipeline run event for pipeline {pipeline.id}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to run pipeline: {e}")

    return pipeline
