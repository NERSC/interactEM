import uuid
from enum import Enum

from pydantic import BaseModel

AgentID, OperatorID, PortID = uuid.UUID, uuid.UUID, uuid.UUID


class MessageSubject(str, Enum):
    DATA = "data"


class BaseMessage(BaseModel):
    subject: MessageSubject


class DataMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.DATA
    data: bytes


MESSAGE_SUBJECT_TO_MODEL: dict[MessageSubject, type[BaseMessage]] = {
    MessageSubject.DATA: DataMessage,
}
