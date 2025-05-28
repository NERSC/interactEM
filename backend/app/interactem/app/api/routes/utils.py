import uuid

from fastapi import APIRouter, HTTPException

from interactem.app.api.deps import CurrentUser
from interactem.app.models import Pipeline

router = APIRouter()


def check_present_and_authorized(
    pipeline: Pipeline | None, current_user: CurrentUser, id: uuid.UUID
) -> Pipeline:
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    if not current_user.is_superuser and (pipeline.owner_id != current_user.id):
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline
