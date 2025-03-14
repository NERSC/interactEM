from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

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
    uri: URI
    status: AgentStatus
    status_message: str | None = None
    tags: list[str] = []
    pipeline_id: str | None = None
    pipeline_assignments: list[UUID] = []
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
