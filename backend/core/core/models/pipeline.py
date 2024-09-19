from collections.abc import Sequence
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from .base import IdType, NodeType, OperatorID, PortID, PortType


class PodmanMountType(str, Enum):
    bind = "bind"
    volume = "volume"
    tmpfs = "tmpfs"



class NetworkMode(str, Enum):
    BRIDGE = "bridge"
    NONE = "none"
    CONTAINER = "container"
    HOST = "host"
    NS = "ns"

    def __str__(self):
        return self.value


class PodmanMount(BaseModel):
    type: PodmanMountType
    source: str
    target: str
    read_only: bool = True


class PipelineNodeJSON(BaseModel):
    id: IdType
    node_type: NodeType


class PortJSON(PipelineNodeJSON):
    node_type: NodeType = NodeType.port
    port_type: PortType
    operator_id: OperatorID
    portkey: str


class InputJSON(PortJSON):
    port_type: PortType = PortType.input


class OutputJSON(PortJSON):
    port_type: PortType = PortType.output


class OperatorJSON(PipelineNodeJSON):
    node_type: NodeType = NodeType.operator
    image: str
    params: dict[str, Any] = {}
    inputs: list[PortID] = []
    outputs: list[PortID] = []
    machine_name: str | None = None
    mounts: list[PodmanMount] = []
    env: dict[str, str] = {}
    command: str | list[str] = []
    network_mode: NetworkMode | None = None


class EdgeJSON(BaseModel):
    input_id: PortID | OperatorID
    output_id: PortID | OperatorID
    num_connections: int = 1


class PipelineJSON(BaseModel):
    id: UUID
    operators: Sequence[OperatorJSON] = []
    ports: Sequence[PortJSON] = []
    edges: Sequence[EdgeJSON] = []


class PipelineAssignment(BaseModel):
    agent_id: IdType
    operators_assigned: list[OperatorID] = []
    pipeline: PipelineJSON
