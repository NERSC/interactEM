from enum import Enum
from typing import Any, Optional, Sequence, Tuple, Type, Union
from uuid import UUID

import numpy as np
from pydantic import BaseModel, ValidationError, model_validator, root_validator
from pydantic_settings import SettingsConfigDict
from typing_extensions import Self

IdType = UUID
DataType = Union[np.ndarray, bytes]
NodeID = IdType
PortID = IdType
PortKey = str


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
    uri: Optional[str] = None
    path: Optional[UUID] = None
    transport_protocol: Optional[ProtocolZmq]
    hostname: Optional[str] = None
    hostname_bind: Optional[str] = None
    interface: Optional[str] = None
    port: Optional[int] = None


class URIZmq(URIBase):
    protocol: Protocol = Protocol.Zmq
    transport_protocol: ProtocolZmq
    hostname: str
    hostname_bind: Optional[str] = None
    interface: Optional[str] = None
    port: int

    def to_connect_address(self) -> str:
        return f"{self.transport_protocol.value}://{self.hostname}:{self.port}"

    def to_bind_address(self) -> str:
        return f"{self.transport_protocol.value}://{self.hostname_bind}:{self.port}"

    def to_interface_address(self) -> str:
        return f"{self.transport_protocol.value}://{self.interface}:{self.port}"

    @model_validator(mode="after")
    def check_either_hostname_bind_or_interface(self) -> Self:
        if self.hostname_bind and self.interface:
            raise ValidationError(
                "Exactly one of hostname_bind or interface must be set (if either set)."
            )
        return self


class URIShmem(URIBase):
    protocol: Protocol = Protocol.Shmem
    path: UUID

    def to_address(self) -> str:
        return f"{self.protocol}://{self.path}"


class MessageSubject(str, Enum):
    URI_ASSIGN = "uri.assign"
    URI_CONNECT = "uri.connect"
    PIPELINE = "pipeline"
    ERROR = "error"


class BaseMessage(BaseModel):
    subject: MessageSubject


class ErrorMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.ERROR
    message: Optional[str]


class URIMessage(BaseMessage, URIBase):
    pass


class URIAssignMessage(URIMessage):
    subject: MessageSubject = MessageSubject.URI_ASSIGN


class URIConnectMessage(URIMessage):
    subject: MessageSubject = MessageSubject.URI_CONNECT


class PipelineMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.PIPELINE
    pipeline: Optional["PipelineJSON"] = None
    node_id: Optional[IdType] = None


MESSAGE_SUBJECT_TO_MODEL: dict[MessageSubject, Type[BaseMessage]] = {
    MessageSubject.URI_ASSIGN: URIAssignMessage,
    MessageSubject.URI_CONNECT: URIConnectMessage,
    MessageSubject.PIPELINE: PipelineMessage,
    MessageSubject.ERROR: ErrorMessage,
}


class PortType(str, Enum):
    Data = "data"
    Binary = "binary"


class PortJSON(BaseModel):
    id: IdType
    key: PortKey


class NodeType(str, Enum):
    Operator = "operator"


class PortPairJSON(BaseModel):
    input: PortJSON
    output: PortJSON

    @classmethod
    def from_ports(cls, input_port: PortJSON, output_port: PortJSON):
        return cls(input=input_port, output=output_port)


class NodeJSON(BaseModel):
    id: IdType
    type: NodeType = NodeType.Operator
    params: dict[str, Any] = {}


class NodePairJSON(BaseModel):
    input: NodeJSON
    output: NodeJSON

    @classmethod
    def from_nodes(cls, input_node: NodeJSON, output_node: NodeJSON):
        return cls(input=input_node, output=output_node)


class EdgeJSON(BaseModel):
    id: IdType
    nodes: NodePairJSON
    ports: PortPairJSON


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
