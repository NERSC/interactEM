import abc
from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from interactem.core.constants import AGENTS, OPERATORS, PIPELINES, PORTS
from interactem.core.models.base import KvKeyMixin
from interactem.core.models.canonical import (
    CanonicalOperatorID,
    CanonicalPipelineID,
    CanonicalPipelineRevisionID,
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
    BUSY = "busy"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"

class ErrorMixin:
    error_messages: list[ErrorMessage] = []

    def add_error(self, message: str) -> None:
        error = ErrorMessage(message=message)
        self.error_messages.append(error)

    def clear_old_errors(self, max_age_seconds: float = 30.0) -> None:
        if not self.error_messages:
            return

        current_time = datetime.now().timestamp()
        self.error_messages = [
            error
            for error in self.error_messages
            if current_time - error.timestamp < max_age_seconds
        ]
        self.maybe_reset_status()

    def clear_errors(self) -> None:
        self.error_messages = []
        self.maybe_reset_status()

    @abc.abstractmethod
    def maybe_reset_status(self) -> None: ...


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

    pipeline_id: str | None = None
    operator_assignments: list[UUID] | None = None
    uptime: float = 0.0

    def maybe_reset_status(self) -> None:
        if not self.error_messages and self.status == AgentStatus.ERROR:
            self.status = AgentStatus.IDLE

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

    def maybe_reset_status(self) -> None:
        if not self.error_messages and self.status == OperatorStatus.ERROR:
            self.status = OperatorStatus.RUNNING

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


class PipelineRunVal(BaseModel, KvKeyMixin):
    id: RuntimePipelineID
    canonical_id: CanonicalPipelineID
    canonical_revision_id: CanonicalPipelineRevisionID

    def key(self) -> str:
        return f"{PIPELINES}.{self.id}"
