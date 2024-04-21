from uuid import uuid4

from zmglue.types import (
    EdgeJSON,
    NodeJSON,
    NodePairJSON,
    NodeType,
    PipelineJSON,
    PortJSON,
    PortPairJSON,
)

NODE_0 = NodeJSON(
    id=uuid4(),
    type=NodeType.Operator,
    params={"hello": "world"},
)

PORT_0 = PortJSON(id=uuid4(), key="hello")

NODE_1 = NodeJSON(
    id=uuid4(),
    type=NodeType.Operator,
    params={"yo": "whattup"},
)

PORT_1 = PortJSON(id=uuid4(), key="hello")

EDGE_0 = EdgeJSON(
    id=uuid4(),
    nodes=NodePairJSON.from_nodes(NODE_0, NODE_1),
    ports=PortPairJSON.from_ports(PORT_0, PORT_1),
)


PORT_2 = PortJSON(id=uuid4(), key="hello")

NODE_2 = NodeJSON(
    id=uuid4(),
    type=NodeType.Operator,
    params={"yo": "whattup"},
)

EDGE_1 = EdgeJSON(
    id=uuid4(),
    nodes=NodePairJSON.from_nodes(NODE_0, NODE_2),
    ports=PortPairJSON.from_ports(PORT_0, PORT_2),
)


PIPELINE = PipelineJSON(
    id=uuid4(),
    nodes=[NODE_0, NODE_1, NODE_2],
    edges=[EDGE_0, EDGE_1],
)
