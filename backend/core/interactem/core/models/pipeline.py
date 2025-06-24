import pathlib
from collections.abc import Sequence
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, model_validator

from ..constants import MOUNT_DIR
from .base import IdType, NodeType, OperatorID, PortID, PortType
from .operators import OperatorParameter, OperatorTag, ParameterName, ParameterType

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

class MountDoesntExistError(Exception):
    def __init__(self, source: pathlib.Path):
        self.source = source
        super().__init__(f"Mount {source} does not exist")

class PodmanMount(BaseModel):
    type: PodmanMountType
    source: str
    target: str
    # TODO: figure out a way to change this in frontend
    read_only: bool = False

    def resolve(self) -> "PodmanMount":
        src = pathlib.Path(self.source).expanduser()
        self.source = str(src)
        target = pathlib.Path(self.target)
        self.target = str(target)

        if not src.exists():
            raise MountDoesntExistError(src)

        return self

    @classmethod
    def from_mount_param(
        cls, parameter: OperatorParameter, use_default=True
    ) -> "PodmanMount":
        if not parameter.type == ParameterType.MOUNT:
            raise ValueError("Parameter must be of type MOUNT")

        if not use_default:
            if not parameter.value:
                raise ValueError(
                    "Parameter value is required when use_default is False"
                )
            src = parameter.value
        else:
            src = parameter.default

        target = f"{MOUNT_DIR}/{parameter.name}"

        return cls(
            type=PodmanMountType.bind,
            source=src,
            target=target,
        )

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
    tags: list[OperatorTag] = []  # Tags for agent matching
    env: dict[str, str] = {}  # Environment variables to pass to the container
    command: str | list[str] = []  # Command to pass to the container
    network_mode: NetworkMode | None = None  # Network mode for the container

    def update_parameter_value(self, name: str, value: str | None) -> None:
        for parameter in self.parameters or []:
            if parameter.name == name:
                parameter.value = value
                return
        raise ValueError(f"Parameter '{name}' not found in operator.")


class OperatorWithMounts(OperatorJSON):
    param_mounts: dict[ParameterName, PodmanMount] = {}  # Container mounts
    internal_mounts: list[PodmanMount] = []  # Other mounts not tied to parameters

    def update_param_mounts(self, use_default: bool = True):
        """
        Update the parameter mounts based on the current parameters.
        If use_default is True, it will use the default value of the parameter.
        """
        if not self.parameters:
            return

        for parameter in self.parameters:
            if not parameter.type == ParameterType.MOUNT:
                continue
            mount = PodmanMount.from_mount_param(parameter, use_default)
            mount = mount.resolve()  # raises MountDoesntExistError
            self.param_mounts[parameter.name] = mount

    @model_validator(mode="after")
    def coerce_params_into_mounts(self) -> "OperatorWithMounts":
        if not self.parameters:
            return self

        # On instantiation, use default values for mounts
        try:
            self.update_param_mounts(use_default=True)
        except MountDoesntExistError as e:
            raise ValueError(
                f"Invalid mount in operator {self.image}: {e.source}"
            ) from e
        return self

    def add_internal_mount(self, mount: PodmanMount) -> None:
        if mount in self.internal_mounts:
            return  # Avoid duplicates
        self.internal_mounts.append(mount)

    @property
    def all_mounts(self) -> list[PodmanMount]:
        return list(self.param_mounts.values()) + self.internal_mounts


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
