import pathlib
from collections.abc import Sequence
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, model_validator

from ..constants import MOUNT_DIR
from .base import IdType, NodeType, OperatorID, PortID, PortType
from .operators import OperatorParameter, ParameterType

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
    # TODO: figure out a way to change this in frontend
    read_only: bool = False

    def resolve(self) -> bool:
        src = pathlib.Path(self.source)
        self.source = str(src)
        target = pathlib.Path(self.target)
        self.target = str(target)
        if src.exists():
            return True
        return False


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
    # tunable parameters for the operator
    parameters: list[OperatorParameter] | None = None
    inputs: list[PortID] = []
    outputs: list[PortID] = []
    machine_name: str | None = None  # Name of the machine to run the operator on
    mounts: list[PodmanMount] = []  # Container mounts
    env: dict[str, str] = {}  # Environment variables to pass to the container
    command: str | list[str] = []  # Command to pass to the container
    network_mode: NetworkMode | None = None  # Network mode for the container

    def validate_mount_for_parameter(
        self, parameter: OperatorParameter, value: str
    ) -> bool:
        if parameter.type != ParameterType.MOUNT:
            return True  # Non-mount parameters don't need this validation

        src = value if value is not None else parameter.default
        # Validate that the source exists
        if not src or not pathlib.Path(src).exists():
            return False
        return True

    def update_mounts_for_parameter(self, parameter: OperatorParameter):
        if parameter.type != ParameterType.MOUNT:
            return

        src = parameter.value if parameter.value is not None else parameter.default
        target = f"{MOUNT_DIR}/{parameter.name}"

        self.mounts = [mount for mount in self.mounts if mount.target != target]

        self.mounts.append(
            PodmanMount(
                type=PodmanMountType.bind,
                source=src,
                target=target,
            )
        )

    @model_validator(mode="after")
    def parameter_to_mount(self):
        if self.parameters is None:
            return self

        for parameter in self.parameters:
            if not parameter.type == ParameterType.MOUNT:
                continue

            if parameter.value:
                src = parameter.value
            else:
                src = parameter.default

            # Skip if the mount is already there
            src_exists = src in [mount.source for mount in self.mounts]
            target_exists = f"{MOUNT_DIR}/{parameter.name}" in [
                mount.target for mount in self.mounts
            ]
            if src_exists and target_exists:
                continue

            if target_exists:
                self.mounts.pop(
                    [mount.target for mount in self.mounts].index(
                        f"{MOUNT_DIR}/{parameter.name}"
                    )
                )
            self.mounts.append(
                PodmanMount(
                    type=PodmanMountType.bind,
                    source=src,
                    target=f"{MOUNT_DIR}/{parameter.name}",
                )
            )
        return self


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
