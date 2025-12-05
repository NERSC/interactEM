from enum import Enum
from typing import Literal

from pydantic import BaseModel

from interactem.core.models.canonical import CanonicalOperatorID
from interactem.core.models.runtime import RuntimePipelineID


class OperatorEventType(str, Enum):
    OPERATOR_RESTART = "operator_restart"


class OperatorEventCreate(BaseModel):
    type: OperatorEventType


class OperatorRestartEvent(BaseModel):
    type: Literal[OperatorEventType.OPERATOR_RESTART] = (
        OperatorEventType.OPERATOR_RESTART
    )
    deployment_id: RuntimePipelineID
    canonical_operator_id: CanonicalOperatorID
