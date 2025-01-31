import datetime
import pathlib
from typing import Self
from uuid import UUID

from pydantic import BaseModel, model_validator
from sfapi_client._models import StatusValue
from sfapi_client._models.job_status_response_squeue import JobStatusResponseSqueue
from sfapi_client.compute import Machine


class StatusRequest(BaseModel):
    machine: Machine


class StatusResponse(BaseModel):
    status: StatusValue


class JobSubmitRequest(BaseModel):
    machine: Machine
    account: str
    qos: str
    constraint: str
    walltime: datetime.timedelta | str
    output: pathlib.Path
    agent_id: UUID
    reservation: str | None = None

    @model_validator(mode="after")
    def format_walltime(self) -> Self:
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


class JobSubmitResponse(BaseModel):
    job: JobStatusResponseSqueue
    jobid: int
    status: StatusValue
