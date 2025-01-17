import uuid
from typing import Any

from pydantic import BaseModel


class PipelineRunEvent(BaseModel):
    id: uuid.UUID
    data: dict[str, Any]
