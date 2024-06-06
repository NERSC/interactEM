from uuid import UUID, uuid4

import pytest

from zmglue.pipeline import Pipeline
from zmglue.types import (
    CommBackend,
    EdgeJSON,
    InputJSON,
    OperatorJSON,
    OutputJSON,
    PipelineJSON,
    PortJSON,
    Protocol,
    URIBase,
    URIConnectMessage,
    URILocation,
    URIUpdateMessage,
)

# Fixtures for nodes and edges


@pytest.fixture
def node0id():
    return UUID("b43a415a-bdb0-4a64-820c-5a1a2a604ec6")


@pytest.fixture
def node1id():
    return UUID("a162db3a-a035-432b-a7ec-8574982ba49d")


@pytest.fixture
def node0output(node0id) -> PortJSON:
    id = uuid4()
    return OutputJSON(
        id=id,
        operator_id=node0id,
        portkey="out0",
        uri=URIBase(
            id=id,
            comm_backend=CommBackend.ZMQ,
            location=URILocation.port,
            hostname="localhost",
            protocol=Protocol.tcp,
        ),
    )


@pytest.fixture
def node1input(node1id) -> PortJSON:
    return InputJSON(
        id=uuid4(),
        operator_id=node1id,
        portkey="in1",
    )


@pytest.fixture
def node0(node0output) -> OperatorJSON:
    id = node0output.operator_id
    return OperatorJSON(
        id=id,
        params={"hello": "world"},
        outputs=[node0output.id],
    )


@pytest.fixture
def node1(node1input) -> OperatorJSON:
    id = node1input.operator_id
    return OperatorJSON(
        id=id,
        params={"hello": "world"},
        inputs=[node1input.id],
    )


@pytest.fixture
def edge0(node0output, node1input) -> EdgeJSON:
    return EdgeJSON(
        input_id=node0output.id,
        output_id=node1input.id,
    )


@pytest.fixture
def edge1(node0, node0output) -> EdgeJSON:
    return EdgeJSON(
        input_id=node0.id,
        output_id=node0output.id,
    )


@pytest.fixture
def edge2(node1input, node1) -> EdgeJSON:
    return EdgeJSON(
        input_id=node1input.id,
        output_id=node1.id,
    )


@pytest.fixture
def edges(edge0, edge1, edge2) -> list[EdgeJSON]:
    return [edge0, edge1, edge2]


@pytest.fixture
def operators(node0, node1) -> list[OperatorJSON]:
    return [node0, node1]


@pytest.fixture
def ports(node0output, node1input) -> list[PortJSON]:
    return [node0output, node1input]


@pytest.fixture
def pipeline(operators, ports, edges) -> PipelineJSON:
    return PipelineJSON(
        id=uuid4(),
        operators=operators,
        ports=ports,
        edges=edges,
    )


def test_pipeline_creation(pipeline):
    p = Pipeline.from_pipeline(pipeline)
    assert p is not None
    assert len(p.nodes) == 4
    assert len(p.edges) == 3


def test_pipeline_to_json(pipeline):
    p = Pipeline.from_pipeline(pipeline)
    json_output = p.to_json()
    assert json_output.id == pipeline.id
    assert len(json_output.operators) == 2
    assert len(json_output.ports) == 2
    assert len(json_output.edges) == 3


def test_get_predecessors(pipeline, node0output, node1input):
    p = Pipeline.from_pipeline(pipeline)
    predecessors = p.get_predecessors(node1input.id)
    assert len(predecessors) == 1
    assert predecessors[0] == node0output.id


def test_get_successors(pipeline, node0, node0output):
    p = Pipeline.from_pipeline(pipeline)
    successors = p.get_successors(node0.id)
    assert len(successors) == 1
    assert successors[0] == node0output.id


def test_update_uri(pipeline, node0output):
    p = Pipeline.from_pipeline(pipeline)
    update_message = URIUpdateMessage(
        id=node0output.id,
        location=URILocation.port,
        comm_backend=CommBackend.ZMQ,
        portkey=node0output.portkey,
        hostname="updated.com",
        interface="eth0",
        port=9090,
    )

    p.update_uri(update_message)
    updated_port = p.nodes[node0output.id]
    updated_uri = updated_port["uri"]

    assert updated_uri.hostname == "updated.com"
    assert updated_uri.port == 9090
    assert updated_uri.interface == "eth0"
    assert updated_uri.protocol == Protocol.tcp


def test_add_node_model_duplicate_error(pipeline, node0):
    p = Pipeline.from_pipeline(pipeline)

    with pytest.raises(ValueError) as excinfo:
        p.add_node_model(node0)
    assert "already exists in the graph" in str(excinfo.value)


def test_add_edge_model_duplicate_error(pipeline, edge0):
    p = Pipeline.from_pipeline(pipeline)
    with pytest.raises(ValueError) as excinfo:
        p.add_edge_model(edge0)  # Attempt to add the same edge again
    assert "already exists in the graph" in str(excinfo.value)


def test_update_uri_partial(pipeline, node0output):
    p = Pipeline.from_pipeline(pipeline)
    initial_uri = node0output.uri
    update_message = URIUpdateMessage(
        id=node0output.id,
        comm_backend=CommBackend.ZMQ,
        location=URILocation.port,
        hostname="updated.com",
    )
    p.update_uri(update_message)
    updated_uri = p.nodes[node0output.id]["uri"]
    assert updated_uri.hostname == "updated.com"
    assert updated_uri.port == initial_uri.port


def test_get_connections(pipeline, node1input):
    p = Pipeline.from_pipeline(pipeline)
    connections = p.get_connections(URIConnectMessage(id=node1input.id))
    print(connections)
    assert len(connections) == 1
    assert connections[0].hostname == "localhost"
