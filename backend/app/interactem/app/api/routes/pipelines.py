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
    PipelineRevisionCreate,
    PipelineRevisionPublic,
    PipelineRevisionUpdate,
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
    # Check pipeline existence and permissions first
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

    # Create the new revision
    revision = PipelineRevision(
        pipeline_id=id,
        revision_id=next_revision_id,
        data=revision_in.data,
    )
    session.add(revision)

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
    revision_id: int,
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
    if not pipeline:
        raise HTTPException(status_code=404, detail="Associated pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    return PipelineRevisionPublic.model_validate(revision)


@router.patch("/{id}/revisions/{revision_id}", response_model=PipelineRevisionPublic)
def update_pipeline_revision(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    revision_id: int,
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
    if not pipeline:
        raise HTTPException(status_code=404, detail="Associated pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")

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
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")
    session.delete(pipeline)
    session.commit()
    return Message(message="Pipeline deleted successfully")


# ...existing code...
@router.post("/{id}/revisions/{revision_id}/run", response_model=PipelineRevisionPublic)
async def run_pipeline(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    revision_id: int,
) -> PipelineRevisionPublic:
    """
    Run a specific revision of a pipeline.
    """
    pipeline_id: uuid.UUID = id

    revision = session.get(PipelineRevision, (id, revision_id))
    if not revision:
        raise HTTPException(status_code=404, detail="Pipeline revision not found")

    pipeline = revision.pipeline
    if not pipeline:
        raise HTTPException(status_code=404, detail="Associated pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not enough permissions")

    run_event_data = {
        "id": revision.pipeline_id,
        "data": revision.data,
        "revision_id": revision.revision_id,
    }

    try:
        event_to_publish = PipelineRunEvent(**run_event_data)
        await publish_pipeline_run_event(event_to_publish)
        logger.info(
            f"Sent publish pipeline run event for pipeline {pipeline_id} using revision {revision_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to publish run event for pipeline {pipeline_id} revision {revision_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=f"Failed to run pipeline: {e}")

    return PipelineRevisionPublic.model_validate(revision)
