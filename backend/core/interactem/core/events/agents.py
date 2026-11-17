import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, RootModel

from interactem.core.models.base import IdType


class AgentControlEventType(StrEnum):
    SHUTDOWN = "agent_shutdown"


class AgentControlBase(BaseModel):
    agent_id: IdType
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )


class AgentShutdownEvent(AgentControlBase):
    type: Literal[AgentControlEventType.SHUTDOWN] = AgentControlEventType.SHUTDOWN


class AgentControlEvent(RootModel):
    root: AgentShutdownEvent = Field(discriminator="type")
