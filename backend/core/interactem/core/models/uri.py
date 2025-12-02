from urllib.parse import parse_qs, urlencode, urlparse
from uuid import UUID

from pydantic import AnyUrl, BaseModel, UrlConstraints, model_validator
from typing_extensions import Self

from ..logger import get_logger
from .base import (
    CommBackend,
    IdType,
    Protocol,
    URILocation,
)

logger = get_logger()


# TODO: could base64 encode this so that we don't clobber "/" and "?" and "=" and "&" in URI
class ZMQAddress(BaseModel):
    protocol: Protocol
    hostname: str | None = None
    port: int | None = None
    interface: str | None = None
    endpoint: str | None = None

    @classmethod
    def _from_uri_cls(cls, uri: "URI") -> list[Self] | Self:
        if uri.comm_backend != CommBackend.ZMQ:
            raise ValueError(
                f"Can't parse URI, incorrect comm backend: {uri.comm_backend}, should be 'zmq'."
            )

        addresses = uri.query.get("address", [])
        if not addresses:
            logger.info("No addresses found in URI.")
            return []

        parsed_addresses = []
        for address in addresses:
            try:
                zmq_address = cls.from_address(address)
                if not zmq_address.hostname:
                    zmq_address.hostname = uri.hostname
                parsed_addresses.append(zmq_address)
            except ValueError as e:
                raise ValueError(f"Failed to parse address '{address}': {e}")

        if len(parsed_addresses) == 1:
            return parsed_addresses[0]
        elif parsed_addresses:
            return parsed_addresses
        else:
            return []

    @classmethod
    def from_uri(cls, uri: "URI |str") -> list[Self] | Self:
        if isinstance(uri, str):
            uri = URI.from_uri(uri)
        return cls._from_uri_cls(uri)

    @classmethod
    def from_address(cls, address: str) -> Self:
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
            if not (self.hostname or self.interface):
                raise ValueError(
                    "tcp protocol requires either hostname or interface to be set."
                )
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
            query_string = urlencode(query_params, doseq=True)
            return f"{self.protocol.value}://?{query_string}"

        elif self.protocol in [Protocol.inproc, Protocol.ipc] and self.endpoint:
            return f"{self.protocol.value}://{self.endpoint}"
        else:
            raise ValueError("Invalid address configuration.")

    def to_connect_address(self) -> str:
        if self.protocol == Protocol.tcp:
            if not self.hostname:
                raise ValueError("Hostname must be set for connecting.")
            if not self.port:
                raise ValueError("Port must be set for TCP connections.")
            return f"{self.protocol.value}://{self.hostname}:{self.port}"
        elif self.protocol in [Protocol.inproc, Protocol.ipc]:
            return f"{self.protocol.value}://{self.endpoint}"
        else:
            raise ValueError("Unsupported protocol.")

    def to_bind_address(self) -> str:
        if self.protocol == Protocol.tcp:
            if not self.interface:
                raise ValueError("Interface must be set for binding.")
            if not self.port:
                return f"{self.protocol.value}://{self.interface}"
            return f"{self.protocol.value}://{self.interface}:{self.port}"
        elif self.protocol in [Protocol.inproc, Protocol.ipc]:
            return f"{self.protocol.value}://{self.endpoint}"
        else:
            raise ValueError("Unsupported protocol.")

    def update_uri(self, uri: "URI") -> bool:
        address_str = self.to_address()
        current_addresses = uri.query.get("address", [])

        if address_str in current_addresses:
            logger.info("Address already present in URI.")
            return False

        current_addresses.append(address_str)
        uri.query["address"] = current_addresses
        return True


class PipelineUrl(AnyUrl):
    # Chose for this to only be a path... since we don't have a "host" for a pipeline
    _constraints = UrlConstraints(
        allowed_schemes=["pipeline"],
        host_required=False,
    )


class OperatorUrl(AnyUrl):
    # We DO have a host for operators, which is the agent
    _constraints = UrlConstraints(
        allowed_schemes=["operator"],
        host_required=True,
    )


class PortUrl(AnyUrl):
    # and also a host for ports, which is the agent
    _constraints = UrlConstraints(
        allowed_schemes=["port"],
        host_required=True,
    )


class PipelineURI(BaseModel):
    """Format: pipeline:///pipeline-uuid/revision-id/runtime-id"""

    pipeline_id: UUID
    revision_id: int
    runtime_id: int

    def to_uri(self) -> PipelineUrl:
        uri_str = f"pipeline:///{self.pipeline_id}/{self.revision_id}/{self.runtime_id}"
        return PipelineUrl(uri_str)

    @classmethod
    def from_uri(cls, uri: str | PipelineUrl) -> "PipelineURI":
        uri = PipelineUrl(uri) if isinstance(uri, str) else uri

        # Parse path components
        if not uri.path:
            raise ValueError("Pipeline URI path is missing")
        path_parts = uri.path.strip("/").split("/")
        if len(path_parts) < 3:
            raise ValueError(
                "Invalid pipeline URI format - expected pipeline_id/revision_id/runtime_id in path"
            )

        try:
            pipeline_id = UUID(path_parts[0])
            revision_id = int(path_parts[1])
            runtime_id = int(path_parts[2])
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid pipeline URI format: {e}") from e

        return cls(
            pipeline_id=pipeline_id, revision_id=revision_id, runtime_id=runtime_id
        )


class OperatorURI(BaseModel):
    """Format: operator://agent-uuid/pipeline-uuid/revision-id/runtime-id/operator-uuid/parallel-index"""

    pipeline_id: UUID
    revision_id: int
    runtime_id: int
    operator_id: UUID
    parallel_index: int
    agent_id: UUID

    def to_uri(self) -> OperatorUrl:
        uri_str = (
            f"operator://{self.agent_id}/"
            f"{self.pipeline_id}/"
            f"{self.revision_id}/"
            f"{self.runtime_id}/"
            f"{self.operator_id}/"
            f"{self.parallel_index}"
        )
        return OperatorUrl(uri_str)

    @classmethod
    def from_uri(cls, uri: str | OperatorUrl) -> "OperatorURI":
        uri = OperatorUrl(uri) if isinstance(uri, str) else uri
        agent_id = UUID(uri.host)

        # Parse path components
        if not uri.path:
            raise ValueError("Operator URI path is missing")
        path_parts = uri.path.strip("/").split("/")
        if len(path_parts) < 5:
            raise ValueError(
                "Invalid operator URI format - expected "
                "pipeline_id/revision_id/runtime_id/operator_id/parallel_index in path"
            )

        try:
            pipeline_id = UUID(path_parts[0])
            revision_id = int(path_parts[1])
            runtime_id = int(path_parts[2])
            operator_id = UUID(path_parts[3])
            parallel_index = int(path_parts[4])
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid operator URI format: {e}") from e

        return cls(
            pipeline_id=pipeline_id,
            revision_id=revision_id,
            runtime_id=runtime_id,
            operator_id=operator_id,
            parallel_index=parallel_index,
            agent_id=agent_id,
        )

    @property
    def pipeline_uri(self) -> PipelineURI:
        return PipelineURI(
            pipeline_id=self.pipeline_id,
            revision_id=self.revision_id,
            runtime_id=self.runtime_id,
        )


class PortURI(BaseModel):
    """Format: port://agent-uuid/pipeline-uuid/revision-id/runtime-id/operator-uuid/parallel-index/port-uuid"""

    pipeline_id: UUID
    revision_id: int
    runtime_id: int
    operator_id: UUID
    parallel_index: int
    port_id: UUID
    agent_id: UUID

    def to_uri(self) -> PortUrl:
        uri_str = (
            f"port://{self.agent_id}/"
            f"{self.pipeline_id}/"
            f"{self.revision_id}/"
            f"{self.runtime_id}/"
            f"{self.operator_id}/"
            f"{self.parallel_index}/"
            f"{self.port_id}"
        )
        return PortUrl(uri_str)

    @classmethod
    def from_uri(cls, uri: str | PortUrl) -> "PortURI":
        uri = PortUrl(uri) if isinstance(uri, str) else uri
        agent_id = UUID(uri.host)

        # Parse path components
        if not uri.path:
            raise ValueError("Port URI path is missing")
        path_parts = uri.path.strip("/").split("/")
        if len(path_parts) < 6:
            raise ValueError(
                "Invalid port URI format - expected "
                "pipeline_id/revision_id/runtime_id/operator_id/parallel_index/port_id in path"
            )

        try:
            pipeline_id = UUID(path_parts[0])
            revision_id = int(path_parts[1])
            runtime_id = int(path_parts[2])
            operator_id = UUID(path_parts[3])
            parallel_index = int(path_parts[4])
            port_id = UUID(path_parts[5])
        except (ValueError, IndexError) as e:
            raise ValueError(f"Invalid port URI format: {e}") from e

        return cls(
            pipeline_id=pipeline_id,
            revision_id=revision_id,
            runtime_id=runtime_id,
            operator_id=operator_id,
            parallel_index=parallel_index,
            port_id=port_id,
            agent_id=agent_id,
        )

    @property
    def operator_uri(self) -> OperatorURI:
        return OperatorURI(
            pipeline_id=self.pipeline_id,
            revision_id=self.revision_id,
            runtime_id=self.runtime_id,
            operator_id=self.operator_id,
            parallel_index=self.parallel_index,
            agent_id=self.agent_id,
        )

    @property
    def pipeline_uri(self) -> PipelineURI:
        return PipelineURI(
            pipeline_id=self.pipeline_id,
            revision_id=self.revision_id,
            runtime_id=self.runtime_id,
        )


# TODO: Probably could subclass AnyUrl instead of BaseModel, get rid of some boilerplate
class URI(BaseModel):
    id: IdType
    location: URILocation
    hostname: str
    comm_backend: CommBackend
    query: dict[str, list[str]] = {}

    def to_uri(self) -> str:
        base_path = f"/{self.location.value}/{self.id}"
        query: str = urlencode(self.query, doseq=True)

        if query:
            return f"{self.comm_backend.value}://{self.hostname}{base_path}?{query}"
        else:
            return f"{self.comm_backend.value}://{self.hostname}{base_path}"

    @classmethod
    def from_uri(cls, uri: str) -> "URI":
        parsed_uri = urlparse(uri)
        query = parse_qs(parsed_uri.query)

        comm_backend = CommBackend(parsed_uri.scheme)

        location, id_str = parsed_uri.path.strip("/").split("/")
        id = UUID(id_str)

        hostname = parsed_uri.hostname
        if not hostname:
            raise ValueError("Hostname must be set in URI.")

        return cls(
            id=id,
            comm_backend=comm_backend,
            location=URILocation(location),
            hostname=hostname,
            query=query,
        )
