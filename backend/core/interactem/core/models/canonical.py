from collections.abc import Sequence

from pydantic import BaseModel, Field

from interactem.core.models.base import IdType, NodeType, PortType
from interactem.core.models.spec import (
    OperatorSpec,
    OperatorSpecID,
    OperatorSpecTag,
    ParallelType,
)

"""
These models represent the canonical form a pipeline. This is what is stored in the db
as json data. Frontend sends this data to app from wired up operators.
"""


CanonicalOperatorID = IdType
CanonicalPortID = IdType
CanonicalPipelineID = IdType
CanonicalPipelineRevisionID = int


class CanonicalPort(BaseModel):
    id: CanonicalPortID  # UID generated at DnD time in frontend
    node_type: NodeType = NodeType.port
    port_type: PortType
    canonical_operator_id: CanonicalOperatorID  # The operator this port belongs to
    portkey: str  # Unused currently, but can be used for port-port compatibility


class CanonicalInput(CanonicalPort):
    port_type: PortType = PortType.input


class CanonicalOutput(CanonicalPort):
    port_type: PortType = PortType.output

class CanonicalOperator(OperatorSpec):
    id: CanonicalOperatorID  # UID generated at DnD time in frontend
    spec_id: OperatorSpecID  # The operator spec ID this operator is based on
    node_type: NodeType = NodeType.operator
    # tunable parameters for the operator
    inputs: list[CanonicalPortID] = []
    outputs: list[CanonicalPortID] = []
    tags: list[OperatorSpecTag] = []
    # amount of copies to be made of this operator. We used 128 as maximum
    # that could be changed, but we don't want to have user misuse this...
    parallelism: int | None = Field(default=None, ge=1, le=128)


class CanonicalEdge(BaseModel):
    input_id: CanonicalPortID | CanonicalOperatorID
    output_id: CanonicalPortID | CanonicalOperatorID


class CanonicalPipelineData(BaseModel):
    operators: Sequence[CanonicalOperator] = []
    ports: Sequence[CanonicalPort] = []
    edges: Sequence[CanonicalEdge] = []


class CanonicalPipeline(CanonicalPipelineData):
    id: CanonicalPipelineID
    revision_id: CanonicalPipelineRevisionID

    def get_operator_by_label(self, label: str) -> CanonicalOperator | None:
        return next((op for op in self.operators if op.label == label), None)

    def get_parallel_operators(self) -> list[CanonicalOperator]:
        return [
            op
            for op in self.operators
            if op.parallel_config and op.parallel_config.type != ParallelType.NONE
        ]

    def get_sequential_operators(self) -> list[CanonicalOperator]:
        return [
            op
            for op in self.operators
            if not op.parallel_config or op.parallel_config.type == ParallelType.NONE
        ]
