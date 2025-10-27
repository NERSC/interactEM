import abc
from enum import Enum
from uuid import UUID

IdType = UUID

class PipelineDeploymentState(str, Enum):
    PENDING = "pending"
    INITIALIZING = "initializing"
    RUNNING = "running"
    DEGRADED = "degraded"
    FAILING = "failing"
    FAILED = "failed"
    FAILED_TO_START = "failed_to_start"
    CANCELLED = "cancelled"

class KvKeyMixin(abc.ABC):
    @abc.abstractmethod
    def key(self) -> str: ...


class CommBackend(str, Enum):
    ZMQ = "zmq"
    MPI = "mpi"
    NATS = "nats"


class Protocol(str, Enum):
    tcp = "tcp"
    inproc = "inproc"
    ipc = "ipc"


class URILocation(str, Enum):
    operator = "operator"
    port = "port"
    agent = "agent"
    orchestrator = "orchestrator"


class PortType(str, Enum):
    input = "input"
    output = "output"


class NodeType(str, Enum):
    operator = "operator"
    port = "port"
