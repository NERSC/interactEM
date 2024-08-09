import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import func, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message,
    Pipeline,
    PipelineCreate,
    PipelinePublic,
    PipelinesPublic,
)

router = APIRouter()


@router.get("/", response_model=PipelinesPublic)
def read_pipelines(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve pipelines.
    """

    if current_user.is_superuser:
        count_statement = select(func.count()).select_from(Pipeline)
        count = session.exec(count_statement).one()
        statement = select(Pipeline).offset(skip).limit(limit)
        pipelines = session.exec(statement).all()
    else:
        count_statement = (
            select(func.count())
            .select_from(Pipeline)
            .where(Pipeline.owner_id == current_user.id)
        )
        count = session.exec(count_statement).one()
        statement = (
            select(Pipeline)
            .where(Pipeline.owner_id == current_user.id)
            .offset(skip)
            .limit(limit)
        )
        pipelines = session.exec(statement).all()

    return PipelinesPublic(data=pipelines, count=count)


@router.get("/{id}", response_model=PipelinePublic)
def read_pipeline(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get pipeline by ID.
    """
    pipeline = session.get(Pipeline, id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=400, detail="Not enough permissions")
    return pipeline


@router.post("/", response_model=PipelinePublic)
def create_pipeline(
    *, session: SessionDep, current_user: CurrentUser, pipeline_in: PipelineCreate
) -> Any:
    """
    Create new pipeline.
    """
    pipeline = Pipeline.model_validate(pipeline_in, update={"owner_id": current_user.id})
    session.add(pipeline)
    session.commit()
    session.refresh(pipeline)
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
        raise HTTPException(status_code=400, detail="Not enough permissions")
    session.delete(pipeline)
    session.commit()
    return Message(message="Pipeline deleted successfully")
