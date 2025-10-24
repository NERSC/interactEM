from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, RootModel

from interactem.core.models.base import PipelineDeploymentState
from interactem.core.models.canonical import (
    CanonicalPipelineID,
    CanonicalPipelineRevisionID,
)
from interactem.core.models.runtime import RuntimePipelineID


class PipelineEventType(str, Enum):
    PIPELINE_RUN = "pipeline_run"
    PIPELINE_STOP = "pipeline_stop"
    PIPELINE_UPDATE = "pipeline_update"


class PipelineRunEvent(BaseModel):
    type: Literal[PipelineEventType.PIPELINE_RUN] = PipelineEventType.PIPELINE_RUN
    canonical_id: CanonicalPipelineID
    revision_id: CanonicalPipelineRevisionID
    deployment_id: RuntimePipelineID
    data: dict[str, Any]


class PipelineStopEvent(BaseModel):
    type: Literal[PipelineEventType.PIPELINE_STOP] = PipelineEventType.PIPELINE_STOP
    deployment_id: RuntimePipelineID


class PipelineUpdateEvent(BaseModel):
    type: Literal[PipelineEventType.PIPELINE_UPDATE] = PipelineEventType.PIPELINE_UPDATE
    deployment_id: RuntimePipelineID
    state: PipelineDeploymentState | None = None


class PipelineEvent(RootModel):
    root: PipelineRunEvent | PipelineStopEvent | PipelineUpdateEvent = Field(
        discriminator="type"
    )
