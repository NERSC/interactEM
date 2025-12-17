import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, model_validator
from sfapi_client._models import StatusValue

class Machine(str, Enum):
    perlmutter = "perlmutter"

class StatusRequest(BaseModel):
    machine: Machine


class StatusResponse(BaseModel):
    status: StatusValue


class ComputeType(str, Enum):
    gpu = "gpu"
    cpu = "cpu"


class AgentCreateEvent(BaseModel):
    machine: Machine
    duration: datetime.timedelta
    compute_type: ComputeType
    num_nodes: int
    extra: dict[str, Any] | None = None


class JobSubmitEvent(BaseModel):
    machine: Machine
    account: str
    qos: str
    constraint: str
    walltime: datetime.timedelta | str
    reservation: str | None = None
    num_nodes: int = 1

    @model_validator(mode="after")
    def format_walltime(self) -> "JobSubmitEvent":
        if isinstance(self.walltime, str):
            # Validate the string format HH:MM:SS
            parts = self.walltime.split(":")
            if len(parts) != 3:
                raise ValueError("Walltime must be in the format HH:MM:SS")
            hours, minutes, seconds = map(int, parts)
            if not (0 <= hours < 24 and 0 <= minutes < 60 and 0 <= seconds < 60):
                raise ValueError("Walltime must represent a valid time.")
            return self

        # Convert the walltime to HH:MM:SS format
        total_seconds = int(self.walltime.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.walltime = f"{hours:02}:{minutes:02}:{seconds:02}"
        return self