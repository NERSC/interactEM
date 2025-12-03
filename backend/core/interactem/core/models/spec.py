from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, RootModel, model_validator

from interactem.core.models.base import IdType

OperatorSpecID = IdType

"""
Models for operator specification. These are implemented by the user and attached
to the container labels.
"""


class OperatorSpecInput(BaseModel):
    name: str  # Name of the input, to be used as parameter name
    label: str  # Human readable name of the input
    description: str  # Human readable description of the input
    type: str  # Type of the input, e.g., BatchedFrames, Frame, etc.


class OperatorSpecOutput(BaseModel):
    name: str  # Name of the input, to be used as parameter name
    label: str  # Human readable name of the input
    description: str  # Human readable description of the input
    type: str  # Type of the input, e.g., BatchedFrames, Frame, etc.


class ParameterSpecType(str, Enum):
    STRING = "str"
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    MOUNT = "mount"
    STR_ENUM = "str-enum"

class ExportParameterSpecType(BaseModel):
    # Unused, just for generation of TypeScript enums
    type: ParameterSpecType

ParameterName = str


class OperatorSpecParameterBase(BaseModel):
    name: ParameterName  # Name of the parameter
    label: str  # Human readable name of the parameter
    description: str  # Human readable description of the parameter
    type: ParameterSpecType  # Type of the parameter
    default: str  # Default value of the parameter
    required: bool  # If the parameter is required


class OperatorSpecParameterString(OperatorSpecParameterBase):
    type: Literal["str"]
    default: str


class OperatorSpecParameterMount(OperatorSpecParameterBase):
    type: Literal["mount"]
    default: str


class OperatorSpecParameterInteger(OperatorSpecParameterBase):
    type: Literal["int"]
    default: int


class OperatorSpecParameterFloat(OperatorSpecParameterBase):
    type: Literal["float"]
    default: float


class OperatorSpecParameterBoolean(OperatorSpecParameterBase):
    type: Literal["bool"]
    default: bool


class OperatorSpecParameterStrEnum(OperatorSpecParameterBase):
    type: Literal["str-enum"]
    default: str
    options: list[str]

    @model_validator(mode="after")
    def check_default_in_options(self):
        if self.default not in self.options:
            raise ValueError(
                f"Default value '{self.default}' for parameter '{self.name}' is not in options."
            )
        return self


class OperatorSpecParameter(RootModel):
    root: (
        OperatorSpecParameterString
        | OperatorSpecParameterMount
        | OperatorSpecParameterInteger
        | OperatorSpecParameterFloat
        | OperatorSpecParameterBoolean
        | OperatorSpecParameterStrEnum
    ) = Field(discriminator="type")


class OperatorSpecTag(BaseModel):
    value: str  # The actual tag value (e.g., "gpu", "ncem-4dstem")
    description: str | None = None


class ParallelType(str, Enum):
    NONE = "none"
    EMBARRASSING = "embarrassing"


class ParallelConfig(BaseModel):
    type: ParallelType = ParallelType.NONE


class OperatorSpec(BaseModel):
    id: OperatorSpecID
    label: str  # Human readable name of the operator
    description: str  # Human readable description of the operator
    image: str  # Contain image for operator
    inputs: list[OperatorSpecInput] | None = None  # List of inputs
    outputs: list[OperatorSpecOutput] | None = None  # List of outputs
    parameters: list[OperatorSpecParameter] | None = None  # List of parameters
    tags: list[OperatorSpecTag] | None = None  # List of tags to match on
    parallel_config: ParallelConfig | None = None  # Parallel execution config
