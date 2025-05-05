import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel


class PipelineEventType(str, Enum):
    PIPELINE_RUN = "pipeline_run"
    PIPELINE_STOP = "pipeline_stop"


class PipelineEvent(BaseModel):
    type: PipelineEventType
    id: uuid.UUID
    revision_id: int


class PipelineRunEvent(PipelineEvent):
    type: PipelineEventType = PipelineEventType.PIPELINE_RUN
    data: dict[str, Any]

class PipelineRunVal(BaseModel):
    id: uuid.UUID
    revision_id: int

class PipelineStopEvent(PipelineEvent):
    type: PipelineEventType = PipelineEventType.PIPELINE_STOP
