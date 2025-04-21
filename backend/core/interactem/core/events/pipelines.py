import uuid
from typing import Any

from pydantic import BaseModel


class PipelineRunEvent(BaseModel):
    id: uuid.UUID
    revision_id: int
    data: dict[str, Any]
