from enum import StrEnum

from pydantic import BaseModel

from .uri import URI


class OperatorStatus(StrEnum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"


class OperatorVal(BaseModel):
    uri: URI
    status: OperatorStatus
    pipeline_id: str | None = None
