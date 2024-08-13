import uuid
from enum import Enum

from pydantic import BaseModel

from .pipeline import PipelineJSON, PipelineNodeJSON
from .uri import URI

AgentID, OperatorID, PortID = uuid.UUID, uuid.UUID, uuid.UUID

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
    connections: list[URI]


class GetConnectionsResponseMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.GET_CONNECTION_ADDRESSES_RESPONSE
    connections: list[str]


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
    pipeline: PipelineJSON | None = None
    node_id: AgentID | OperatorID | None = None


class PutPipelineNodeMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.PIPELINE_UPDATE
    node: PipelineNodeJSON


class OKMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.OK
    message: str | None


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
