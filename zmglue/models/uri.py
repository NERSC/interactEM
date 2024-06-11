from uuid import UUID
from urllib.parse import parse_qs, urlencode, urlparse
from pydantic import BaseModel, ValidationError, model_validator
from typing_extensions import Self

from .base import CommBackend, Protocol, URILocation, PortKey

class URIBase(BaseModel):
    id: UUID
    location: URILocation
    hostname: str
    comm_backend: CommBackend
    protocol: Protocol | None = None
    interface: str | None = None
    port: int | None = None
    hostname_bind: str | None = None
    portkey: PortKey | None = None

    def to_uri(self) -> str:
        base_path = f"/{self.location.value}/{self.id}"
        query_params = {
            "protocol": (self.protocol.value if self.protocol else None),
            "port": self.port,
            "interface": self.interface,
            "hostname_bind": self.hostname_bind,
            "portkey": self.portkey,
        }
        query_string = urlencode(
            {k: v for k, v in query_params.items() if v is not None}
        )
        return f"{self.comm_backend.value}://{self.hostname}{base_path}?{query_string}"

    @classmethod
    def from_uri(cls, uri: str) -> "URIBase":
        parsed_uri = urlparse(uri)
        query_params = parse_qs(parsed_uri.query)

        comm_backend = CommBackend(parsed_uri.scheme)

        location, id_str = parsed_uri.path.strip("/").split("/")
        id = UUID(id_str)

        hostname = parsed_uri.hostname
        if not hostname:
            raise ValueError("Hostname must be set in URI.")

        protocol = query_params.get("protocol", [None])[0]
        protocol = Protocol(protocol) if protocol else None

        port = query_params.get("port", [0])[0]
        port = int(port) if port else None

        interface = query_params.get("interface", [None])[0]
        hostname_bind = query_params.get("hostname_bind", [None])[0]
        portkey = query_params.get("portkey", [None])[0]

        base = cls(
            id=id,
            comm_backend=comm_backend,
            location=URILocation(location),
            hostname=hostname,
            protocol=protocol,
            port=port,
            interface=interface,
            hostname_bind=hostname_bind,
            portkey=portkey,
        )

        if comm_backend == CommBackend.ZMQ:
            if portkey:
                specific_class = URIZmqPort
            else:
                specific_class = URIZmq
        elif comm_backend == CommBackend.MPI:
            specific_class = URIMPI
        else:
            return base

        return specific_class(**base.model_dump())

class URIZmq(URIBase):
    protocol: Protocol  # type: ignore
    port: int  # type: ignore
    hostname_bind: str | None = None
    interface: str | None = None
    comm_backend: CommBackend = CommBackend.ZMQ

    def to_connect_address(self) -> str:
        if not self.hostname:
            raise ValueError("Hostname must be set to generate connect address.")
        return f"{self.protocol.value}://{self.hostname}:{self.port}"

    def to_bind_address(self) -> str:
        if self.hostname_bind:
            return f"{self.protocol.value}://{self.hostname_bind}:{self.port}"
        elif self.interface:
            return f"{self.protocol.value}://{self.interface}:{self.port}"
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
    portkey: PortKey  # type: ignore
    location: URILocation = URILocation.port

class URIMPI(URIBase):
    protocol: Protocol | None = None  # MPI doesn't use transport protocol
    port: int | None = None  # MPI doesn't use port
    hostname_bind: str | None = None
    interface: str | None = None

    def to_connect_address(self) -> str:
        return f"mpi://{self.hostname}"

    @classmethod
    def from_uri(cls, uri: str) -> "URIMPI":
        base = super().from_uri(uri)
        return cls(**base.model_dump())
