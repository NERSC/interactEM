from enum import Enum

from pydantic import BaseModel

from .uri import URI


class PortStatus(str, Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"


class PortVal(BaseModel):
    uri: URI
    status: PortStatus
