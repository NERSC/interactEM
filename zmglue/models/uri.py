from sys import prefix
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse
from uuid import UUID

from pydantic import BaseModel, IPvAnyAddress, model_validator
from typing_extensions import Self

from .base import (
    AgentID,
    CommBackend,
    OperatorID,
    OrchestratorID,
    PortID,
    Protocol,
    URILocation,
)


class ZMQAddress(BaseModel):
    protocol: Protocol
    hostname: Optional[str] = None
    port: Optional[int] = None
    interface: Optional[str] = None
    endpoint: Optional[str] = None

    @classmethod
    def from_address(cls, address: str) -> "ZMQAddress":
        parsed_url = urlparse(address)
        protocol = parsed_url.scheme

        if protocol == "tcp":
            query_params = parse_qs(parsed_url.query)
            hostname = query_params.get("hostname", [None])[0]
            interface = query_params.get("interface", [None])[0]
            port = query_params.get("port", [None])[0]
            port = int(port) if port else None

            return cls(
                protocol=Protocol.tcp, hostname=hostname, interface=interface, port=port
            )

        elif protocol in ["inproc", "ipc"]:
            endpoint = parsed_url.netloc + parsed_url.path
            if not endpoint:
                raise ValueError(f"{protocol} protocol requires an endpoint to be set.")
            return cls(protocol=Protocol(protocol), endpoint=endpoint)
        else:
            raise ValueError("Invalid address protocol.")

    @model_validator(mode="after")
    def protocol_correctness(self) -> Self:
        if self.protocol in [Protocol.inproc, Protocol.ipc]:
            if not self.endpoint:
                raise ValueError("inproc and ipc protocols require endpoint to be set.")
            if self.hostname or self.port or self.interface:
                raise ValueError(
                    "ipc/inproc protocols do not use hostname or port. Please use endpoint instead."
                )

        elif self.protocol == Protocol.tcp:
            if not (self.hostname or self.interface) or not self.port:
                raise ValueError("tcp protocol requires hostname and port to be set.")
        return self

    def to_address(self) -> str:
        query_params = {}
        if self.protocol == Protocol.tcp:
            if self.hostname:
                query_params["hostname"] = self.hostname
            if self.interface:
                query_params["interface"] = self.interface
            if self.port:
                query_params["port"] = str(self.port)
            query_string = urlencode(query_params)
            return f"{self.protocol.value}://?{query_string}"

        elif self.protocol in [Protocol.inproc, Protocol.ipc] and self.endpoint:
            return f"{self.protocol.value}://{self.endpoint}"
        else:
            raise ValueError("Invalid address configuration.")

    def to_connect_address(self) -> str:
        if self.protocol == Protocol.tcp:
            if not self.hostname:
                raise ValueError("Hostname must be set for connecting.")
            return f"{self.protocol.value}://{self.hostname}:{self.port}"
        elif self.protocol in [Protocol.inproc, Protocol.ipc]:
            return f"{self.protocol.value}://{self.endpoint}"
        else:
            raise ValueError("Unsupported protocol.")

    def to_bind_address(self) -> str:
        if self.protocol == Protocol.tcp:
            if not self.interface:
                raise ValueError("Interface must be set for binding.")
            return f"{self.protocol.value}://{self.interface}:{self.port}"
        elif self.protocol in [Protocol.inproc, Protocol.ipc]:
            return f"{self.protocol.value}://{self.endpoint}"
        else:
            raise ValueError("Unsupported protocol.")


class URI(BaseModel):
    id: PortID | OperatorID | AgentID | OrchestratorID
    location: URILocation
    hostname: str
    comm_backend: CommBackend
    address: ZMQAddress | None = None

    def to_uri(self) -> str:
        base_path = f"/{self.location.value}/{self.id}"
        query_params = {}
        if self.comm_backend == CommBackend.ZMQ and self.address:
            query_params["address"] = self.address.to_address()
        query_string = urlencode(
            {k: v for k, v in query_params.items() if v is not None}
        )

        if query_string:
            return (
                f"{self.comm_backend.value}://{self.hostname}{base_path}?{query_string}"
            )
        else:
            return f"{self.comm_backend.value}://{self.hostname}{base_path}"

    @classmethod
    def from_uri(cls, uri: str) -> "URI":
        parsed_uri = urlparse(uri)
        query_params = parse_qs(parsed_uri.query)

        comm_backend = CommBackend(parsed_uri.scheme)

        location, id_str = parsed_uri.path.strip("/").split("/")
        id = UUID(id_str)

        hostname = parsed_uri.hostname
        if not hostname:
            raise ValueError("Hostname must be set in URI.")

        address: ZMQAddress | None = None
        if comm_backend == CommBackend.ZMQ:
            _address = query_params.get("address", [None])[0]
            if _address and _address.strip():  # Ensure it's not empty
                address = ZMQAddress.from_address(_address)

        return cls(
            id=id,
            comm_backend=comm_backend,
            location=URILocation(location),
            hostname=hostname,
            address=address,
        )
