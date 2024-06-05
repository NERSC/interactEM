from collections.abc import Sequence
from enum import Enum
from typing import Any, Optional
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import UUID

from pydantic import BaseModel, ValidationError, model_validator
from typing_extensions import Self

IdType = UUID
NodeID = IdType
PortID = IdType
PortKey = str


class Protocol(str, Enum):
    Zmq = "zmq"


class ProtocolZmq(str, Enum):
    tcp = "tcp"
    inproc = "inproc"
    ipc = "ipc"


class URILocation(str, Enum):
    node = "node"
    agent = "agent"
    orchestrator = "orchestrator"


class URIBase(BaseModel):
    id: UUID
    location: URILocation
    hostname: str
    protocol: Protocol = Protocol.Zmq
    transport_protocol: ProtocolZmq | None = None
    interface: str | None = None
    port: int | None = None
    hostname_bind: str | None = None
    portkey: PortKey | None = None

    def to_uri(self) -> str:
        base_path = f"/{self.location.value}/{self.id}"
        query_params = {
            "transport_protocol": (
                self.transport_protocol.value if self.transport_protocol else None
            ),
            "port": self.port,
            "interface": self.interface,
            "hostname_bind": self.hostname_bind,
            "portkey": self.portkey,
        }
        query_string = urlencode(
            {k: v for k, v in query_params.items() if v is not None}
        )
        return f"{self.protocol.value}://{self.hostname}{base_path}?{query_string}"

    @classmethod
    def from_uri(cls, uri: str) -> "URIBase":
        parsed_uri = urlparse(uri)
        query_params = parse_qs(parsed_uri.query)

        protocol = Protocol(parsed_uri.scheme)

        location, id_str = parsed_uri.path.strip("/").split("/")
        id = UUID(id_str)

        hostname = parsed_uri.hostname
        if not hostname:
            raise ValueError("Hostname must be set in URI.")

        transport_protocol = query_params.get("transport_protocol", [None])[0]
        transport_protocol = (
            ProtocolZmq(transport_protocol) if transport_protocol else None
        )

        port = query_params.get("port", [0])[0]
        port = int(port) if port else None

        interface = query_params.get("interface", [None])[0]
        hostname_bind = query_params.get("hostname_bind", [None])[0]
        portkey = query_params.get("portkey", [None])[0]

        base = cls(
            id=id,
            protocol=protocol,
            location=URILocation(location),
            hostname=hostname,
            transport_protocol=transport_protocol,
            port=port,
            interface=interface,
            hostname_bind=hostname_bind,
            portkey=portkey,
        )

        if portkey:
            specific_class = URIZmqPort
        elif transport_protocol:
            specific_class = URIZmq
        else:
            return base

        return specific_class(**base.model_dump())


class URIZmq(URIBase):
    transport_protocol: ProtocolZmq
    port: int
    hostname_bind: str | None = None
    interface: str | None = None

    def to_connect_address(self) -> str:
        if not self.hostname:
            raise ValueError("Hostname must be set to generate connect address.")
        return f"{self.transport_protocol.value}://{self.hostname}:{self.port}"

    def to_bind_address(self) -> str:
        if self.hostname_bind:
            return f"{self.transport_protocol.value}://{self.hostname_bind}:{self.port}"
        elif self.interface:
            return f"{self.transport_protocol.value}://{self.interface}:{self.port}"
        else:
            raise ValueError(
                "Either hostname_bind or interface must be set to generate bind address."
            )

    @classmethod
    def from_uri(cls, uri: str) -> "URIZmq":
        base = super().from_uri(uri)
        return cls(**base.model_dump())

    @model_validator(mode="after")
    def check_either_hostname_bind_or_interface(self) -> Self:
        if self.hostname_bind and self.interface:
            raise ValidationError(
                "Exactly one of hostname_bind or interface must be set."
            )
        return self


class URIZmqPort(URIZmq):
    portkey: PortKey
    location: URILocation = URILocation.node


class MessageSubject(str, Enum):
    URI_UPDATE = "uri.update"
    URI_CONNECT = "uri.connect"
    URI_CONNECT_RESPONSE = "uri.connect.response"
    DATA = "data"
    SHMEM = "shmem"
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
    connections: list[URIBase]


class URIUpdateMessage(URIMessage):
    subject: MessageSubject = MessageSubject.URI_UPDATE


class URIConnectMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.URI_CONNECT
    id: UUID


class PipelineMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.PIPELINE
    pipeline: Optional["PipelineJSON"] = None
    node_id: IdType | None = None


class DataMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.DATA
    data: bytes


class ShmMessage(BaseMessage):
    subject: MessageSubject = MessageSubject.SHMEM
    name: str
    size: int


MESSAGE_SUBJECT_TO_MODEL: dict[MessageSubject, type[BaseMessage]] = {
    MessageSubject.URI_UPDATE: URIUpdateMessage,
    MessageSubject.URI_CONNECT: URIConnectMessage,
    MessageSubject.PIPELINE: PipelineMessage,
    MessageSubject.ERROR: ErrorMessage,
    MessageSubject.DATA: DataMessage,
    MessageSubject.SHMEM: ShmMessage,
    MessageSubject.URI_CONNECT_RESPONSE: URIConnectResponseMessage,
}


class PortType(str, Enum):
    input = "input"
    output = "output"


class NodeType(str, Enum):
    operator = "operator"
    port = "port"


class PipelineNodeJSON(BaseModel):
    id: IdType
    node_type: NodeType


class PortJSON(PipelineNodeJSON):
    id: IdType
    node_type: NodeType = NodeType.port
    port_type: PortType
    node_id: IdType
    portkey: PortKey
    uri: Optional[URIBase] = None


class InputJSON(PortJSON):
    port_type: PortType = PortType.input


class OutputJSON(PortJSON):
    port_type: PortType = PortType.output
    uri: URIBase


class OperatorJSON(PipelineNodeJSON):
    id: IdType
    node_type: NodeType = NodeType.operator
    params: dict[str, Any] = {}
    inputs: list[IdType] = []
    outputs: list[IdType] = []


class EdgeJSON(BaseModel):
    input_id: IdType
    output_id: IdType


class PipelineJSON(BaseModel):
    id: IdType
    operators: Sequence[OperatorJSON] = []
    ports: Sequence[PortJSON] = []
    edges: Sequence[EdgeJSON] = []
