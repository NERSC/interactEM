from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from .pipeline import PipelineJSON
from .uri import URIBase


class MessageSubject(str, Enum):
    URI_UPDATE = "uri.update"
    URI_CONNECT = "uri.connect"
    URI_CONNECT_RESPONSE = "uri.connect.response"
    DATA = "data"
    PIPELINE = "pipeline"
    ERROR = "error"


class BaseMessage(BaseModel):
    subject: MessageSubject


class ErrorMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.ERROR
    message: str | None


class URIMessage(BaseMessage, URIBase):
    pass


class URIConnectResponseMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.URI_CONNECT_RESPONSE
    connections: List[URIBase]


class URIUpdateMessage(URIMessage):
    subject: MessageSubject = MessageSubject.URI_UPDATE


class URIConnectMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.URI_CONNECT
    id: UUID


class PipelineMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.PIPELINE
    pipeline: Optional[PipelineJSON] = None
    node_id: UUID | None = None


class DataMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.DATA
    data: bytes


MESSAGE_SUBJECT_TO_MODEL: dict[MessageSubject, type[BaseMessage]] = {
    MessageSubject.URI_UPDATE: URIUpdateMessage,
    MessageSubject.URI_CONNECT: URIConnectMessage,
    MessageSubject.PIPELINE: PipelineMessage,
    MessageSubject.ERROR: ErrorMessage,
    MessageSubject.DATA: DataMessage,
    MessageSubject.URI_CONNECT_RESPONSE: URIConnectResponseMessage,
}
