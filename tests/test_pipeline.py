from uuid import UUID

import pytest
from core.models import (
    URI,
    CommBackend,
    EdgeJSON,
    OperatorJSON,
    PipelineJSON,
    Protocol,
    URIConnectMessage,
    URILocation,
    URIUpdateMessage,
)
from core.models.uri import ZMQAddress
from core.pipeline import Pipeline


# Test to ensure pipeline creation from JSON is correct
def test_pipeline_creation(pipeline: PipelineJSON):
    p = Pipeline.from_pipeline(pipeline)
    assert p is not None
    assert len(p.operators) == 3
    assert len(p.ports) == 4
    assert len(p.edges) == 6


# Test to ensure pipeline to JSON conversion works
def test_pipeline_to_json(pipeline: PipelineJSON):
    p = Pipeline.from_pipeline(pipeline)
    json_output = p.to_json()
    assert json_output.id == pipeline.id
    assert len(json_output.operators) == len(pipeline.operators)
    assert len(json_output.ports) == len(pipeline.ports)
    assert len(json_output.edges) == len(pipeline.edges)


# Test to ensure predecessor nodes are fetched correctly
def test_get_predecessors(
    pipeline: PipelineJSON, operator_1_input_0_id: UUID, operator_0_output_0_id: UUID
):
    p = Pipeline.from_pipeline(pipeline)
    predecessors = p.get_predecessors(operator_1_input_0_id)
    assert len(predecessors) == 1
    assert predecessors[0] == operator_0_output_0_id


# Test to ensure successor nodes are fetched correctly
def test_get_successors(
    pipeline: PipelineJSON, operator_0_id: UUID, operator_0_output_0_id: UUID
):
    p = Pipeline.from_pipeline(pipeline)
    successors = p.get_successors(operator_0_id)
    assert len(successors) == 2
    assert successors[0] == operator_0_output_0_id


# Test to ensure URI update functionality works as expected
def test_update_uri(pipeline: PipelineJSON, operator_0_output_0_id: UUID):
    p = Pipeline.from_pipeline(pipeline)
    update_message = URIUpdateMessage(
        id=operator_0_output_0_id,
        location=URILocation.port,
        comm_backend=CommBackend.ZMQ,
        hostname="updated.com",
        query={
            "address": [
                ZMQAddress(
                    protocol=Protocol.tcp,
                    hostname="updated.com",
                    port=9090,
                    interface="eth0",
                ).to_address()
            ]
        },
    )
    p.update_uri(update_message)
    updated_port = p.nodes[operator_0_output_0_id]
    updated_uri = updated_port["uri"]
    updated_uri = URI(**updated_uri)
    assert isinstance(updated_uri.query, dict)
    assert updated_uri.query["address"]
    addresses = updated_uri.query["address"]
    assert len(addresses) == 1
    address = ZMQAddress.from_address(addresses[0])
    assert address.hostname == "updated.com"
    assert address.port == 9090
    assert address.interface == "eth0"
    assert address.protocol == Protocol.tcp


# Test to ensure adding a duplicate node raises an error
def test_add_node_model_duplicate_error(
    pipeline: PipelineJSON, operator_0: OperatorJSON
):
    p = Pipeline.from_pipeline(pipeline)
    with pytest.raises(ValueError) as excinfo:
        p.add_node_model(operator_0)
    assert "already exists in the graph" in str(excinfo.value)


# Test to ensure adding a duplicate edge raises an error
def test_add_edge_model_duplicate_error(pipeline: PipelineJSON, edge_0: EdgeJSON):
    p = Pipeline.from_pipeline(pipeline)
    with pytest.raises(ValueError) as excinfo:
        p.add_edge_model(edge_0)
    assert "already exists in the graph" in str(excinfo.value)


# Test to ensure partial URI update works
def test_update_uri_partial(pipeline: PipelineJSON, operator_0_output_0_id: UUID):
    p = Pipeline.from_pipeline(pipeline)
    initial_uri = p.nodes[operator_0_output_0_id]["uri"]
    initial_uri = URI(**initial_uri)
    update_message = URIUpdateMessage(
        id=operator_0_output_0_id,
        comm_backend=CommBackend.ZMQ,
        location=URILocation.port,
        hostname="updated.com",
        query={
            "address": [
                ZMQAddress(
                    protocol=Protocol.tcp, interface="eth0", port=5555
                ).to_address()
            ]
        },
    )
    p.update_uri(update_message)
    updated_uri = p.nodes[operator_0_output_0_id]["uri"]
    updated_uri = URI(**updated_uri)
    assert updated_uri.hostname == "updated.com"


# Test to ensure partial URI update works
def test_update_no_address(pipeline: PipelineJSON, operator_0_output_0_id: UUID):
    p = Pipeline.from_pipeline(pipeline)
    initial_uri = p.nodes[operator_0_output_0_id]["uri"]
    initial_uri = URI(**initial_uri)
    update_message = URIUpdateMessage(
        id=operator_0_output_0_id,
        comm_backend=CommBackend.ZMQ,
        location=URILocation.port,
        hostname="sam.com",
    )
    p.update_uri(update_message)
    updated_uri = p.nodes[operator_0_output_0_id]["uri"]
    updated_uri = URI(**updated_uri)
    assert updated_uri.hostname == "sam.com"


# Test to ensure connections for a given port ID are fetched correctly
def test_get_connections(
    pipeline: PipelineJSON, operator_1_input_0_id: UUID, operator_0_output_0_id: UUID
):
    p = Pipeline.from_pipeline(pipeline)
    connections = p.get_connections(URIConnectMessage(id=operator_1_input_0_id))
    assert len(connections) == 1
    assert connections[0].hostname == "localhost"
    assert connections[0].id == operator_0_output_0_id
