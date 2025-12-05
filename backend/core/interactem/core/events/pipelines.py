import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, RootModel

from interactem.core.events.operators import OperatorRestartEvent
from interactem.core.models.base import IdType, PipelineDeploymentState
from interactem.core.models.canonical import (
    CanonicalOperatorID,
    CanonicalPipelineID,
    CanonicalPipelineRevisionID,
)
from interactem.core.models.runtime import (
    PipelineAssignment,
    RuntimePipelineID,
)


class PipelineEventType(str, Enum):
    PIPELINE_RUN = "pipeline_run"
    PIPELINE_STOP = "pipeline_stop"
    PIPELINE_UPDATE = "pipeline_update"
    PIPELINE_ASSIGNMENTS = "pipeline_assignments"


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
    state: PipelineDeploymentState
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class PipelineAssignmentsEvent(BaseModel):
    type: Literal[PipelineEventType.PIPELINE_ASSIGNMENTS] = (
        PipelineEventType.PIPELINE_ASSIGNMENTS
    )
    deployment_id: RuntimePipelineID
    assignments: list[PipelineAssignment]


class PipelineEvent(RootModel):
    root: (
        PipelineRunEvent
        | PipelineStopEvent
        | PipelineUpdateEvent
        | PipelineAssignmentsEvent
        | OperatorRestartEvent
    ) = Field(discriminator="type")


class AgentPipelineEventType(str, Enum):
    START = "agent_start"
    STOP = "agent_stop"
    RESTART_OPERATOR = "agent_restart_operator"


class AgentPipelineBase(BaseModel):
    agent_id: IdType
    deployment_id: RuntimePipelineID


class AgentPipelineRunEvent(AgentPipelineBase):
    type: Literal[AgentPipelineEventType.START] = AgentPipelineEventType.START
    assignment: PipelineAssignment


class AgentPipelineStopEvent(AgentPipelineBase):
    type: Literal[AgentPipelineEventType.STOP] = AgentPipelineEventType.STOP


class AgentOperatorRestartEvent(AgentPipelineBase):
    type: Literal[AgentPipelineEventType.RESTART_OPERATOR] = (
        AgentPipelineEventType.RESTART_OPERATOR
    )
    canonical_operator_id: CanonicalOperatorID


class AgentPipelineEvent(RootModel):
    root: (
        AgentPipelineRunEvent
        | AgentPipelineStopEvent
        | AgentOperatorRestartEvent
    ) = Field(discriminator="type")
