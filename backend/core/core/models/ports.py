from enum import StrEnum

from pydantic import BaseModel

from .uri import URI


class PortStatus(StrEnum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"


class PortVal(BaseModel):
    uri: URI
    status: PortStatus
