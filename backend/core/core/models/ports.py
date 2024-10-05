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

    def __add__(self, other: "PortMetrics") -> "PortMetrics":
        if self.id != other.id:
            raise ValueError("Cannot add PortMetrics with different ids")

        return PortMetrics(
            id=self.id,
            send_count=self.send_count + other.send_count,
            send_bytes=self.send_bytes + other.send_bytes,
            send_timeouts=self.send_timeouts + other.send_timeouts,
            recv_count=self.recv_count + other.recv_count,
            recv_bytes=self.recv_bytes + other.recv_bytes,
            recv_timeouts=self.recv_timeouts + other.recv_timeouts,
        )

    @classmethod
    def combine(cls, others: list["PortMetrics"]) -> "PortMetrics":
        if not others:
            raise ValueError("Cannot combine an empty list of PortMetrics")
        for other in others:
            if others[0].id != other.id:
                raise ValueError("Cannot combine PortMetrics with different ids")
        initial = PortMetrics(id=others[0].id)  # Initial value with the same id
        return sum(others, initial)


class PortMetricsParallel(PortMetrics):
    parallel_idx: int


class PortVal(BaseModel):
    id: IdType
    uri: URI | None = None
    status: PortStatus | None = None
