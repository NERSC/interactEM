import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, RootModel

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


class DeploymentEventType(str, Enum):
    RUN = "deployment_run"
    STOP = "deployment_stop"
    UPDATE = "deployment_update"
    ASSIGNMENTS = "deployment_assignments"
    OPERATOR_RESTART = "operator_restart"


class DeploymentRunEvent(BaseModel):
    type: Literal[DeploymentEventType.RUN] = DeploymentEventType.RUN
    canonical_id: CanonicalPipelineID
    revision_id: CanonicalPipelineRevisionID
    deployment_id: RuntimePipelineID
    data: dict[str, Any]


class DeploymentStopEvent(BaseModel):
    type: Literal[DeploymentEventType.STOP] = DeploymentEventType.STOP
    deployment_id: RuntimePipelineID


class DeploymentUpdateEvent(BaseModel):
    type: Literal[DeploymentEventType.UPDATE] = DeploymentEventType.UPDATE
    deployment_id: RuntimePipelineID
    state: PipelineDeploymentState
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )


class DeploymentAssignmentsEvent(BaseModel):
    type: Literal[DeploymentEventType.ASSIGNMENTS] = (
        DeploymentEventType.ASSIGNMENTS
    )
    deployment_id: RuntimePipelineID
    assignments: list[PipelineAssignment]


class OperatorRestartEvent(BaseModel):
    type: Literal[DeploymentEventType.OPERATOR_RESTART] = (
        DeploymentEventType.OPERATOR_RESTART
    )
    deployment_id: RuntimePipelineID
    canonical_operator_id: CanonicalOperatorID


class OperatorEventCreate(BaseModel):
    type: DeploymentEventType


class DeploymentEvent(RootModel):
    root: (
        DeploymentRunEvent
        | DeploymentStopEvent
        | DeploymentUpdateEvent
        | DeploymentAssignmentsEvent
        | OperatorRestartEvent
    ) = Field(discriminator="type")


class AgentDeploymentEventType(str, Enum):
    START = "agent_deployment_start"
    STOP = "agent_deployment_stop"
    RESTART_OPERATOR = "agent_deployment_restart_operator"


class AgentDeploymentBase(BaseModel):
    agent_id: IdType
    deployment_id: RuntimePipelineID


class AgentDeploymentRunEvent(AgentDeploymentBase):
    type: Literal[AgentDeploymentEventType.START] = AgentDeploymentEventType.START
    assignment: PipelineAssignment


class AgentDeploymentStopEvent(AgentDeploymentBase):
    type: Literal[AgentDeploymentEventType.STOP] = AgentDeploymentEventType.STOP


class AgentOperatorRestartEvent(AgentDeploymentBase):
    type: Literal[AgentDeploymentEventType.RESTART_OPERATOR] = (
        AgentDeploymentEventType.RESTART_OPERATOR
    )
    canonical_operator_id: CanonicalOperatorID


class AgentDeploymentEvent(RootModel):
    root: (
        AgentDeploymentRunEvent
        | AgentDeploymentStopEvent
        | AgentOperatorRestartEvent
    ) = Field(discriminator="type")
