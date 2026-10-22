import abc
from enum import StrEnum
from uuid import UUID

IdType = UUID


class PipelineDeploymentState(StrEnum):
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


class CommBackend(StrEnum):
    ZMQ = "zmq"
    MPI = "mpi"
    NATS = "nats"


class Protocol(StrEnum):
    tcp = "tcp"
    inproc = "inproc"
    ipc = "ipc"


class URILocation(StrEnum):
    operator = "operator"
    port = "port"
    agent = "agent"
    orchestrator = "orchestrator"


class PortType(StrEnum):
    input = "input"
    output = "output"


class NodeType(StrEnum):
    operator = "operator"
    port = "port"
