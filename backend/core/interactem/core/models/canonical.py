from collections.abc import Sequence

from pydantic import BaseModel

from interactem.core.models.base import IdType, NodeType, PortType
from interactem.core.models.spec import OperatorSpec, OperatorSpecID, OperatorSpecTag

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


class CanonicalEdge(BaseModel):
    input_id: CanonicalPortID | CanonicalOperatorID
    output_id: CanonicalPortID | CanonicalOperatorID


class CanonicalPipelineData(BaseModel):
    operators: Sequence[CanonicalOperator] = []
    ports: Sequence[CanonicalPort] = []
    edges: Sequence[CanonicalEdge] = []


class CanonicalPipeline(CanonicalPipelineData):
    id: CanonicalPipelineID
    revision_id: int
