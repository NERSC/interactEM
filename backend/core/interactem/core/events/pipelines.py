from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import UUID

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
    OPERATOR_FAILURE = "operator_failure"


class OperatorFailureType(str, Enum):
    STARTUP_FAILED = "startup_failed"
    MAX_RESTARTS_EXCEEDED = "max_restarts_exceeded"


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


class OperatorFailureEvent(BaseModel):
    """
    Event published by an agent when an operator fails to start or restart.
    """
    type: Literal[PipelineEventType.OPERATOR_FAILURE] = PipelineEventType.OPERATOR_FAILURE
    deployment_id: RuntimePipelineID
    operator_id: UUID
    agent_id: UUID
    failure_type: OperatorFailureType
    error_message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PipelineEvent(RootModel):
    root: PipelineRunEvent | PipelineStopEvent | PipelineUpdateEvent | OperatorFailureEvent = Field(
        discriminator="type"
    )
