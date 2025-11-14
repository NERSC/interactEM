import abc
from enum import Enum
from uuid import UUID

IdType = UUID

class PipelineDeploymentState(str, Enum):
    PENDING = "pending"
    AGENTS_ASSIGNED = "assigned_agents"
    FAILED_TO_START = "failed_to_start"
    FAILURE_ON_AGENT = "failure_on_agent"
    RUNNING = "running"
    CANCELLED = "cancelled"

TERMINAL_DEPLOYMENT_STATES = [
    PipelineDeploymentState.CANCELLED,
    PipelineDeploymentState.FAILED_TO_START,
]

RUNNING_DEPLOYMENT_STATES = [
    PipelineDeploymentState.RUNNING,
]


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
