from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from interactem.core.constants import AGENTS, OPERATORS, PORTS
from interactem.core.models.base import KvKeyMixin
from interactem.core.models.canonical import (
    CanonicalOperatorID,
    CanonicalPipelineID,
    CanonicalPortID,
)
from interactem.core.models.runtime import (
    RuntimeOperatorID,
    RuntimePipelineID,
    RuntimePortID,
)
from interactem.core.models.uri import URI


class ErrorMessage(BaseModel):
    message: str
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())


class AgentStatus(str, Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    CLEANING_OPERATORS = "cleaning_operators"
    OPERATORS_STARTING = "operators_starting"
    DEPLOYMENT_RUNNING = "running_deployment"
    DEPLOYMENT_ERROR = "deployment_error"
    SHUTTING_DOWN = "shutting_down"


class ErrorMixin:
    error_messages: list[ErrorMessage] = []

    def add_error(self, message: str) -> None:
        error = ErrorMessage(message=message)
        self.error_messages.append(error)

    def clear_errors(self) -> None:
        self.error_messages = []


class AgentVal(BaseModel, KvKeyMixin, ErrorMixin):
    name: str | None = None
    uri: URI
    status: AgentStatus
    status_message: str | None = None

    # Orchestrator matches agent tags with operator tags
    tags: list[str] = []

    # Orchestrator prefers to avoid crossing network boundaries after
    # crossing once
    networks: set[str]

    current_deployment_id: UUID | None = None
    operator_assignments: list[UUID] | None = None
    uptime: float = 0.0

    @model_validator(mode="after")
    def check_has_networks(self) -> "AgentVal":
        if not self.networks:
            raise ValueError("Agent must have at least one network.")
        return self

    def key(self) -> str:
        return f"{AGENTS}.{self.uri.id}"


class OperatorStatus(str, Enum):
    INITIALIZING = "initializing"
    RUNNING = "running"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"


class OperatorVal(BaseModel, KvKeyMixin, ErrorMixin):
    id: RuntimeOperatorID
    canonical_id: CanonicalOperatorID
    status: OperatorStatus
    canonical_pipeline_id: CanonicalPipelineID
    runtime_pipeline_id: RuntimePipelineID

    def key(self) -> str:
        return f"{OPERATORS}.{self.id}"


class PortStatus(str, Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"


class PortVal(BaseModel, KvKeyMixin):
    id: RuntimePortID
    canonical_id: CanonicalPortID
    uri: URI | None = None
    status: PortStatus | None = None

    def key(self) -> str:
        return f"{PORTS}.{self.id}"
