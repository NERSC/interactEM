from enum import Enum

from pydantic import BaseModel

from core.models.base import IdType

from .uri import URI


class PortStatus(str, Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"


class PortMetrics(BaseModel):
    id: IdType
    send_count: int = 0
    send_bytes: int = 0
    send_timeouts: int = 0
    recv_count: int = 0
    recv_bytes: int = 0
    recv_timeouts: int = 0


class PortVal(BaseModel):
    id: IdType
    uri: URI | None = None
    status: PortStatus | None = None
