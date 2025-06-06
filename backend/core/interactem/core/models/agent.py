from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .uri import URI


class AgentStatus(str, Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    SHUTTING_DOWN = "shutting_down"


class ErrorMessage(BaseModel):
    message: str
    timestamp: float = Field(default_factory=lambda: datetime.now().timestamp())


class AgentVal(BaseModel):
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

        if not self.error_messages:
            if self.status == AgentStatus.ERROR:
                self.status = AgentStatus.IDLE

    @model_validator(mode="after")
    def check_has_networks(self) -> "AgentVal":
        if not self.networks:
            raise ValueError("Agent must have at least one network.")
        return self
