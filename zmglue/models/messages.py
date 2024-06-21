from enum import Enum
from typing import List, Optional

from pydantic import BaseModel

from zmglue.models.base import AgentID, OperatorID, PortID

from .pipeline import PipelineJSON, PipelineNodeJSON
from .uri import URI


class MessageSubject(str, Enum):
    URI_UPDATE = "uri.update"
    URI_CONNECT = "uri.connect"
    URI_CONNECT_RESPONSE = "uri.connect.response"
    GET_CONNECTION_ADDRESSES_RESPONSE = "uri.get_connection_addresses.response"
    GET_CONNECTION_ADDRESSES = "uri.get_connection_addresses"
    DATA = "data"
    PIPELINE = "pipeline"
    ERROR = "error"
    PIPELINE_UPDATE = "pipeline.update"
    OK = "ok"


class BaseMessage(BaseModel):
    subject: MessageSubject


class ErrorMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.ERROR
    message: str | None


class URIMessage(BaseMessage, URI):
    pass


class URIConnectResponseMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.URI_CONNECT_RESPONSE
    connections: List[URI]


class GetConnectionsResponseMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.GET_CONNECTION_ADDRESSES_RESPONSE
    connections: List[str]


class GetConnectionsMessage(BaseMessage):
    id: PortID
    subject: MessageSubject = MessageSubject.GET_CONNECTION_ADDRESSES


class URIUpdateMessage(URIMessage):
    subject: MessageSubject = MessageSubject.URI_UPDATE


class URIConnectMessage(BaseMessage):
    id: PortID
    subject: MessageSubject = MessageSubject.URI_CONNECT


class PipelineMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.PIPELINE
    pipeline: Optional[PipelineJSON] = None
    node_id: AgentID | OperatorID | None = None


class PutPipelineNodeMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.PIPELINE_UPDATE
    node: PipelineNodeJSON


class OKMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.OK
    message: Optional[str]


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
    MessageSubject.GET_CONNECTION_ADDRESSES_RESPONSE: GetConnectionsResponseMessage,
    MessageSubject.GET_CONNECTION_ADDRESSES: GetConnectionsMessage,
    MessageSubject.PIPELINE_UPDATE: PutPipelineNodeMessage,
    MessageSubject.OK: OKMessage,
}
