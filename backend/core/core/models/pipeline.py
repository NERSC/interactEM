from collections.abc import Sequence
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from .base import IdType, NodeType, OperatorID, PortID, PortType
from .uri import URI


class PipelineNodeJSON(BaseModel):
    id: IdType
    node_type: NodeType
    uri: URI
    connected: bool = False


class PortJSON(PipelineNodeJSON):
    node_type: NodeType = NodeType.port
    port_type: PortType
    operator_id: OperatorID
    portkey: str


class InputJSON(PortJSON):
    port_type: PortType = PortType.input


class OutputJSON(PortJSON):
    port_type: PortType = PortType.output


class OperatorJSON(PipelineNodeJSON):
    node_type: NodeType = NodeType.operator
    image: str
    params: dict[str, Any] = {}
    inputs: list[PortID] = []
    outputs: list[PortID] = []


class EdgeJSON(BaseModel):
    input_id: PortID | OperatorID
    output_id: PortID | OperatorID
    num_connections: int = 1


class PipelineJSON(BaseModel):
    id: UUID
    operators: Sequence[OperatorJSON] = []
    ports: Sequence[PortJSON] = []
    edges: Sequence[EdgeJSON] = []
