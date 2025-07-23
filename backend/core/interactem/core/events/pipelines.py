from enum import Enum
from typing import Any

from pydantic import BaseModel

from interactem.core.models.base import PipelineDeploymentState
from interactem.core.models.canonical import CanonicalPipelineID
from interactem.core.models.runtime import RuntimePipelineID


class PipelineEventType(str, Enum):
    PIPELINE_RUN = "pipeline_run"
    PIPELINE_STOP = "pipeline_stop"
    PIPELINE_UPDATE = "pipeline_update"


class PipelineEvent(BaseModel):
    type: PipelineEventType


class PipelineDeploymentEvent(PipelineEvent):
    type: PipelineEventType = PipelineEventType.PIPELINE_RUN
    canonical_id: CanonicalPipelineID
    revision_id: int
    deployment_id: RuntimePipelineID
    data: dict[str, Any]

class PipelineStopEvent(PipelineEvent):
    type: PipelineEventType = PipelineEventType.PIPELINE_STOP
    deployment_id: RuntimePipelineID


class PipelineUpdateEvent(PipelineEvent):
    type: PipelineEventType = PipelineEventType.PIPELINE_UPDATE
    deployment_id: RuntimePipelineID
    state: PipelineDeploymentState | None = None
