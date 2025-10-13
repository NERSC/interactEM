from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict

from .runtime import IdType, RuntimeOperatorID


class LogType(str, Enum):
    AGENT = "agent"
    OPERATOR = "operator"
    VECTOR = "vector"


class AgentLog(BaseModel):
    model_config: ConfigDict = ConfigDict(extra="ignore")
    agent_id: IdType
    host: str
    log_type: LogType
    level: str
    log: str
    module: str
    timestamp: datetime


class OperatorLog(BaseModel):
    model_config: ConfigDict = ConfigDict(extra="ignore")
    agent_id: IdType
    deployment_id: IdType
    operator_id: RuntimeOperatorID
    host: str
    level: str
    log: str
    log_type: LogType
    module: str
    timestamp: datetime
