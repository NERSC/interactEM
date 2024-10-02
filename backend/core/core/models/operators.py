from enum import Enum

from pydantic import BaseModel

from .uri import URI


class OperatorStatus(str, Enum):
    INITIALIZING = "initializing"
    IDLE = "idle"
    BUSY = "busy"


class OperatorVal(BaseModel):
    uri: URI
    status: OperatorStatus
    pipeline_id: str | None = None


class OperatorInput(BaseModel):
    label: str # Human readable name of the input
    description: str # Human readable description of the input


class OperatorOutput(BaseModel):
    label: str # Human readable name of the output
    description: str # Human readable description of the output


class OperatorParameter(BaseModel):
    label: str # Human readable name of the parameter
    description: str # Human readable description of the parameter
    type: str # Type of the parameter
    default: str # Default value of the parameter
    required: bool # If the parameter is required


class Operator(BaseModel):
    label: str # Human readable name of the operator
    description: str # Human readable description of the operator
    image: str # Contain image for operator
    inputs: list[OperatorInput] # List of inputs
    outputs: list[OperatorOutput] # List of outputs
    parameters: dict[str, OperatorParameter] # List of parameters
