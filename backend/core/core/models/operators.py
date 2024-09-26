from datetime import datetime, timedelta
from enum import Enum
from logging import Logger

from pydantic import BaseModel, model_validator

from core.models.base import IdType

from .uri import URI


class OperatorStatus(str, Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"

class OperatorTiming(BaseModel):
    before_recv: datetime | None = None
    before_kernel: datetime | None = None
    after_kernel: datetime | None = None
    after_send: datetime | None = None

    @model_validator(mode="after")
    def check_order(self):
        if self.before_recv and self.before_kernel and self.after_kernel:
            if (
                self.before_recv > self.before_kernel
                or self.before_kernel > self.after_kernel
            ):
                raise ValueError("Timing values are out of order")
        return self

    def time_to_recv(self) -> timedelta | None:
        if self.before_recv and self.before_kernel:
            return self.before_kernel - self.before_recv
        return None

    def time_to_kernel(self) -> timedelta | None:
        if self.before_kernel and self.after_kernel:
            return self.after_kernel - self.before_kernel
        return None

    def time_to_send(self) -> timedelta | None:
        if self.after_kernel and self.after_send:
            return self.after_send - self.after_kernel
        return None

    def total_time(self) -> timedelta | None:
        if self.before_recv and self.after_send:
            return self.after_send - self.before_recv
        return None

    def print_timing_info(self, logger: Logger):
        time_to_recv = self.time_to_recv()
        time_to_kernel = self.time_to_kernel()
        time_to_send = self.time_to_send()
        total_time = self.total_time()

        if time_to_recv:
            logger.info(
                f"  Time to receive: {time_to_recv.total_seconds():.6f} seconds"
            )
        if time_to_kernel:
            logger.info(
                f"  Time to run kernel: {time_to_kernel.total_seconds():.6f} seconds"
            )
        if time_to_send:
            logger.info(f"  Time to send: {time_to_send.total_seconds():.6f} seconds")
        if total_time:
            logger.info(f"  Total time: {total_time.total_seconds():.6f} seconds")


class OperatorMetrics(BaseModel):
    id: IdType
    timing: OperatorTiming


class OperatorVal(BaseModel):
    uri: URI
    status: OperatorStatus
    pipeline_id: str | None = None
