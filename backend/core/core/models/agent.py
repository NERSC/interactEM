from enum import Enum

from pydantic import BaseModel

from .uri import URI


class AgentStatus(str, Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"


class AgentVal(BaseModel):
    uri: URI
    status: AgentStatus
    machine_name: str
    pipeline_id: str | None = None
