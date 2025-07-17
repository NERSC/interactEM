from enum import Enum

from pydantic import BaseModel

from interactem.core.models.base import IdType

OperatorSpecID = IdType

"""
Models for operator specification. These are implemented by the user and attached
to the container labels.
"""


class OperatorSpecInput(BaseModel):
    label: str  # Human readable name of the input
    description: str  # Human readable description of the input


class OperatorSpecOutput(BaseModel):
    label: str  # Human readable name of the output
    description: str  # Human readable description of the output


class ParameterSpecType(str, Enum):
    STRING = "str"
    INTEGER = "int"
    FLOAT = "float"
    BOOLEAN = "bool"
    MOUNT = "mount"
    STR_ENUM = "str-enum"


ParameterName = str


class OperatorSpecParameter(BaseModel):
    name: ParameterName  # Name of the parameter
    label: str  # Human readable name of the parameter
    description: str  # Human readable description of the parameter
    type: ParameterSpecType  # Type of the parameter
    default: str  # Default value of the parameter
    required: bool  # If the parameter is required
    value: str | None = None  # Value of the parameter
    options: list[str] | None = None  # List of options for STR_ENUM


class OperatorSpecTag(BaseModel):
    value: str  # The actual tag value (e.g., "gpu", "ncem-4dstem")
    description: str | None = None


class ParallelType(str, Enum):
    NONE = "none"
    EMBARASSING = "embarrassing"


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
