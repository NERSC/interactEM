from mimetypes import init
from uuid import UUID

import pytest

from zmglue.pipeline import Pipeline
from zmglue.types import (
    CommBackend,
    EdgeJSON,
    OperatorJSON,
    PipelineJSON,
    Protocol,
    URIBase,
    URIConnectMessage,
    URILocation,
    URIUpdateMessage,
)


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
        interface="eth0",
        protocol=Protocol.tcp,
        port=9090,
    )
    p.update_uri(update_message)
    updated_port = p.nodes[operator_0_output_0_id]
    updated_uri = updated_port["uri"]

    assert updated_uri.hostname == "updated.com"
    assert updated_uri.port == 9090
    assert updated_uri.interface == "eth0"
    assert updated_uri.protocol == Protocol.tcp


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
    initial_uri = URIBase(**initial_uri)
    update_message = URIUpdateMessage(
        id=operator_0_output_0_id,
        comm_backend=CommBackend.ZMQ,
        location=URILocation.port,
        hostname="updated.com",
    )
    p.update_uri(update_message)
    updated_uri = p.nodes[operator_0_output_0_id]["uri"]

    assert updated_uri.hostname == "updated.com"
    assert updated_uri.port == initial_uri.port


# Test to ensure connections for a given port ID are fetched correctly
def test_get_connections(
    pipeline: PipelineJSON, operator_1_input_0_id: UUID, operator_0_output_0_id: UUID
):
    p = Pipeline.from_pipeline(pipeline)
    connections = p.get_connections(URIConnectMessage(id=operator_1_input_0_id))
    assert len(connections) == 1
    assert connections[0].hostname == "localhost"
    assert connections[0].id == operator_0_output_0_id
