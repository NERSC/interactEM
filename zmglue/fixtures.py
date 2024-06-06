from uuid import uuid4

from zmglue.types import EdgeJSON, PipelineJSON, Protocol, URIBase, URILocation

NODE_0_ID = uuid4()
NODE_0 = NodeJSON(
    id=NODE_0_ID,
    params={"hello": "world"},
    outputs={
        "out1": URIBase(
            id=NODE_0_ID,
            location=URILocation.node,
            hostname="localhost",
            interface="lo0",
            protocol=Protocol.tcp,
            portkey="out1",
        )
    },
)

NODE_1_ID = uuid4()
NODE_1 = NodeJSON(id=NODE_1_ID, params={"hello": "world"}, inputs=["in1"])

EDGE_0 = EdgeJSON(
    nodes=NodePair(input_id=NODE_0.id, output_id=NODE_1.id),
    ports=PortPair(input_portkey="out1", output_portkey="in1"),
)


PIPELINE = PipelineJSON(
    id=uuid4(),
    nodes=[NODE_0, NODE_1],
    edges=[EDGE_0],
)
