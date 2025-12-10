from enum import Enum

from pydantic import BaseModel

from interactem.core.models.canonical import CanonicalOperatorID


class TriggerInvocation(BaseModel):
    canonical_operator_id: CanonicalOperatorID
    trigger: str


class TriggerInvocationRequest(BaseModel):
    trigger: str


class TriggerInvocationResponseStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


class TriggerInvocationResponse(BaseModel):
    status: TriggerInvocationResponseStatus
    message: str | None = None
