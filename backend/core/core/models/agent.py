from enum import StrEnum

from pydantic import BaseModel

from .uri import URI


class AgentStatus(StrEnum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"


class AgentVal(BaseModel):
    uri: URI
    status: AgentStatus
    pipeline_id: str | None = None
