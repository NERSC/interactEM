from collections.abc import Sequence

from pydantic import BaseModel

from interactem.core.models.base import IdType, NodeType, PortType
from interactem.core.models.spec import (
    OperatorSpecID,
    OperatorSpecParameter,
    OperatorSpecTag,
    ParallelConfig,
)

"""
These models represent the canonical form a pipeline. This is what is stored in the db
as json data. Frontend sends this data to app from wired up operators.
"""


CanonicalOperatorID = OperatorSpecID
CanonicalPortID = IdType
CanonicalPipelineID = IdType
CanonicalPipelineRevisionID = int


class CanonicalPort(BaseModel):
    id: CanonicalPortID
    node_type: NodeType = NodeType.port
    port_type: PortType
    operator_id: OperatorSpecID  # The operator this port belongs to
    portkey: str  # Unused currently, but can be used for port-port compatibility


class CanonicalInput(CanonicalPort):
    port_type: PortType = PortType.input


class CanonicalOutput(CanonicalPort):
    port_type: PortType = PortType.output


class CanonicalOperator(BaseModel):
    id: CanonicalOperatorID
    node_type: NodeType = NodeType.operator
    image: str  # Container image
    # tunable parameters for the operator
    parameters: list[OperatorSpecParameter] | None = None
    inputs: list[CanonicalPortID] = []
    outputs: list[CanonicalPortID] = []
    tags: list[OperatorSpecTag] = []  # Tags for agent matching
    parallel_config: ParallelConfig | None = None  # Parallel execution configuration

    def update_parameter_value(self, name: str, value: str | None) -> None:
        for parameter in self.parameters or []:
            if parameter.name == name:
                parameter.value = value
                return
        raise ValueError(f"Parameter '{name}' not found in operator.")


class CanonicalEdge(BaseModel):
    input_id: CanonicalPortID | CanonicalOperatorID
    output_id: CanonicalPortID | CanonicalOperatorID


class CanonicalPipeline(BaseModel):
    id: CanonicalPipelineID
    revision_id: int
    operators: Sequence[CanonicalOperator] = []
    ports: Sequence[CanonicalPort] = []
    edges: Sequence[CanonicalEdge] = []
