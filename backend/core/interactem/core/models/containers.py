import pathlib
from enum import Enum

from pydantic import BaseModel, model_validator

from interactem.core.constants import MOUNT_DIR
from interactem.core.models.spec import (
    OperatorSpecParameter,
    ParameterName,
    ParameterSpecType,
)


class NetworkMode(str, Enum):
    BRIDGE = "bridge"
    NONE = "none"
    CONTAINER = "container"
    HOST = "host"
    NS = "ns"

    def __str__(self):
        return self.value


class PodmanMountType(str, Enum):
    bind = "bind"
    volume = "volume"
    tmpfs = "tmpfs"

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
        cls, parameter: OperatorSpecParameter, use_default=True
    ) -> "PodmanMount":
        if not parameter.type == ParameterSpecType.MOUNT:
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


class MountMixin(BaseModel):
    parameters: list[OperatorSpecParameter] | None = None
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
            if not parameter.type == ParameterSpecType.MOUNT:
                continue
            mount = PodmanMount.from_mount_param(parameter, use_default)
            mount = mount.resolve()  # raises MountDoesntExistError
            self.param_mounts[parameter.name] = mount

    @model_validator(mode="after")
    def coerce_params_into_mounts(self) -> "MountMixin":
        if not self.parameters:
            return self

        # On instantiation, use default values for mounts
        try:
            self.update_param_mounts(use_default=True)
        except MountDoesntExistError as e:
            raise ValueError(
                f"Invalid mount: {e.source}"
            ) from e
        return self

    def add_internal_mount(self, mount: PodmanMount) -> None:
        if mount in self.internal_mounts:
            return  # Avoid duplicates
        self.internal_mounts.append(mount)

    @property
    def all_mounts(self) -> list[PodmanMount]:
        return list(self.param_mounts.values()) + self.internal_mounts
