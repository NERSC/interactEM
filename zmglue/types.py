from enum import Enum
from typing import Any, Optional, Sequence, Type, Union
from uuid import UUID

import numpy as np
from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict

IdType = Union[str, UUID]
PortKey = str
DataType = Union[np.ndarray, bytes]
NodeID = IdType


class Protocol(str, Enum):
    Shmem = "shmem"
    Zmq = "zmq"


class ProtocolZmq(str, Enum):
    tcp = "tcp"
    inproc = "inproc"
    ipc = "ipc"


class URIBase(BaseModel):
    node_id: IdType
    port_id: IdType
    protocol: Protocol
    uri: str | None = None
    path: UUID | None = None
    transport_protocol: ProtocolZmq | None = None
    hostname: str | None = None
    port: int | None = None


class URIZmq(URIBase):
    protocol: Protocol = Protocol.Zmq
    transport_protocol: ProtocolZmq
    hostname: str
    port: int

    def to_address(self) -> str:
        return f"{self.transport_protocol}://{self.hostname}:{self.port}"


class URIShmem(URIBase):
    protocol: Protocol = Protocol.Shmem
    path: UUID

    def to_address(self) -> str:
        return f"{self.protocol}://{self.path}"


class MessageType(str, Enum):
    URI_ASSIGN = "uri.assign"
    URI_CONNECT = "uri.connect"
    PIPELINE = "pipeline"


class BaseMessage(BaseModel):
    type: MessageType


class URIMessage(BaseMessage, URIBase):
    pass


class URIAssignMessage(URIMessage):
    type: MessageType = MessageType.URI_ASSIGN


class URIConnectMessage(URIMessage):
    type: MessageType = MessageType.URI_CONNECT


class PipelineMessage(BaseMessage):
    type: MessageType = MessageType.PIPELINE
    pipeline: "PipelineJSON | None" = None


MESSAGE_TYPE_TO_MODEL: dict[MessageType, Type[BaseMessage]] = {
    MessageType.URI_ASSIGN: URIAssignMessage,
    MessageType.URI_CONNECT: URIConnectMessage,
    MessageType.PIPELINE: PipelineMessage,
}


class PortType(str, Enum):
    Data = "data"
    Binary = "binary"


class PortJSON(BaseModel):
    id: IdType
    port: PortKey


class NodeType(str, Enum):
    Operator = "operator"


class NodeJSON(BaseModel):
    id: IdType
    type: NodeType = NodeType.Operator
    image: str
    params: dict[str, Any] = {}


class EdgeJSON(BaseModel):
    type: PortType
    start: NodeID
    stop: NodeID


class PipelineJSON(BaseModel):
    id: IdType
    nodes: Sequence[NodeJSON] = []
    edges: Sequence[EdgeJSON] = []


## Random stuff


class MessageMeta(BaseModel):
    dataset_uuid: UUID
    shape: tuple
    dtype: str
    size: int


class DataMessage(BaseMessage):
    meta: MessageMeta
    data: Optional[bytes]


class Port(BaseModel):
    model_config = SettingsConfigDict(arbitrary_types_allowed=True)
    meta: Optional[dict[str, Any]] = None
    data: Optional[DataType] = None
