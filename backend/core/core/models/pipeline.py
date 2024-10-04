from collections.abc import Sequence
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from .base import IdType, NodeType, OperatorID, PortID, PortType

"""
Pipelines are a DAG of Operators and Ports
We have to have some way of saying that

OperatorA -> OutputPortA -> InputPortB -> OperatorB

and

OperatorA -> OutputPortB -> InputPortC -> OperatorC

In other words, we cannot have a direct connection between
two operators because there needs to be some way of identifying
a specific output port of an operator to a specific input port of another operator
If we think of a better way to do this in the future, we can change it
"""

class PodmanMountType(str, Enum):
    bind = "bind"
    volume = "volume"
    tmpfs = "tmpfs"

    def __str__(self):
        return self.value


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

# Nodes are Operators/Ports
class PipelineNodeJSON(BaseModel):
    id: IdType
    node_type: NodeType

# Ports are Inputs/Outputs
class PortJSON(PipelineNodeJSON):
    node_type: NodeType = NodeType.port
    port_type: PortType
    operator_id: OperatorID  # The operator this port belongs to
    portkey: str  # Unused currently, but can be used for port-port compatibility


class InputJSON(PortJSON):
    port_type: PortType = PortType.input


class OutputJSON(PortJSON):
    port_type: PortType = PortType.output


class OperatorJSON(PipelineNodeJSON):
    node_type: NodeType = NodeType.operator
    image: str  # Container image
    params: dict[str, Any] = {}  # tunable parameters for the operator
    inputs: list[PortID] = []
    outputs: list[PortID] = []
    machine_name: str | None = None  # Name of the machine to run the operator on
    mounts: list[PodmanMount] = []  # Container mounts
    env: dict[str, str] = {}  # Environment variables to pass to the container
    command: str | list[str] = []  # Command to pass to the container
    network_mode: NetworkMode | None = None  # Network mode for the container


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
