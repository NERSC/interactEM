import uuid
from enum import Enum

from pydantic import BaseModel


class OperatorEventType(str, Enum):
    OPERATOR_RUNNING = "running"
    OPERATOR_STOPPED = "stopped"
    OPERATOR_ERROR = "error"


class OperatorErrorType(str, Enum):
    PROCESSING = "processing"


class OperatorEvent(BaseModel):
    type: OperatorEventType
    operator_id: uuid.UUID


class OperatorErrorEvent(OperatorEvent):
    type: OperatorEventType = OperatorEventType.OPERATOR_ERROR
    error_type: OperatorErrorType
    message: str | None = None


class OperatorRunningEvent(OperatorEvent):
    type: OperatorEventType = OperatorEventType.OPERATOR_RUNNING
