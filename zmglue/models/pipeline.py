from typing import Any, List, Sequence
from uuid import UUID

from pydantic import BaseModel

from .base import IdType, NodeType, PortType
from .uri import URIBase


class PipelineNodeJSON(BaseModel):
    id: IdType
    node_type: NodeType
    uri: URIBase


class PortJSON(PipelineNodeJSON):
    node_type: NodeType = NodeType.port
    port_type: PortType
    operator_id: IdType
    portkey: str


class InputJSON(PortJSON):
    port_type: PortType = PortType.input


class OutputJSON(PortJSON):
    port_type: PortType = PortType.output


class OperatorJSON(PipelineNodeJSON):
    node_type: NodeType = NodeType.operator
    params: dict[str, Any] = {}
    inputs: List[UUID] = []
    outputs: List[UUID] = []


class EdgeJSON(BaseModel):
    input_id: UUID
    output_id: UUID


class PipelineJSON(BaseModel):
    id: UUID
    operators: Sequence[OperatorJSON] = []
    ports: Sequence[PortJSON] = []
    edges: Sequence[EdgeJSON] = []
