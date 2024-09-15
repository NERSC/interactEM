from enum import Enum

from pydantic import BaseModel

from .uri import URI


class OperatorStatus(str, Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"


class OperatorVal(BaseModel):
    uri: URI
    status: OperatorStatus
    pipeline_id: str | None = None
